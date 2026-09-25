import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
ASSIST_ROLES = {"reception", "doctor", "nurse", "manager", "finance", "admin"}

# Every assistant answer has the same shape: a short summary plus suggested
# next steps. Note structuring adds proposed chart fields.
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "steps"],
    "additionalProperties": False,
}
NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "chief_complaint": {"type": "string"},
        "assessment": {"type": "string"},
        "plan": {"type": "string"},
        "diagnosis_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"code": {"type": "string"}, "description": {"type": "string"}},
                "required": ["code", "description"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "steps", "chief_complaint", "assessment", "plan", "diagnosis_suggestions"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are CareOS Intelligence, an assistant inside a clinic operations system.
You help staff understand information that is already in the record. You never diagnose, prescribe,
or make clinical decisions: everything you write is reviewed by a qualified person before anyone acts on it.
Write plainly and briefly for busy clinic staff. Use only the facts provided; if something important is
missing, say so instead of guessing. The data is de-identified; refer to "the patient".
Suggested next steps are administrative or review actions for the staff member, not treatment orders."""

TASKS = {
    "patient": ("Summarize this patient's record for a clinician opening the chart: current problems, allergies, "
                "medications, recent visits and results, and anything that needs attention.", SUMMARY_SCHEMA),
    "encounter": ("Structure the clinician's free-text documentation of this visit into chief complaint, assessment "
                  "and plan, using the clinician's own statements only. Propose ICD-10-style codes only for "
                  "diagnoses the clinician explicitly wrote; leave the list empty otherwise.", NOTE_SCHEMA),
    "reception": ("Give the front desk a short picture of today at this branch: volume, who is waiting and for how "
                  "long, and what needs attention next.", SUMMARY_SCHEMA),
    "manager": ("Give the clinic manager an operational insight from these month-to-date figures: what stands out, "
                "possible causes worth checking, and concrete operational follow-ups.", SUMMARY_SCHEMA),
    "invoice": ("Explain this invoice's status for the front desk: what was billed, what was paid, the balance, "
                "and the next billing step.", SUMMARY_SCHEMA),
}
TITLES = {
    "patient": "AI patient summary",
    "encounter": "AI clinical note structuring",
    "reception": "AI assistant — today at a glance",
    "manager": "CareOS Intelligence — operational insight",
    "invoice": "AI billing summary",
}


class CareosAiSuggestion(models.Model):
    """Audit trail of every AI output: what was asked, what came back, and
    what a human did with it (spec: AI-generated → human-reviewed → applied)."""

    _name = "careos.ai.suggestion"
    _description = "CareOS AI Suggestion"
    _order = "create_date desc, id desc"

    kind = fields.Selection([(k, k) for k in TASKS], required=True)
    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    status = fields.Selection([("generated", "AI-generated"), ("applied", "Human-reviewed · applied"),
                               ("dismissed", "Dismissed")], required=True, default="generated")
    output = fields.Json()
    model_used = fields.Char()
    request_id = fields.Char()
    reviewed_by_id = fields.Many2one("res.users", readonly=True)
    reviewed_at = fields.Datetime(readonly=True)

    def _careos_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "kind": self.kind,
            "title": TITLES[self.kind],
            "status": self.status,
            "status_label": dict(self._fields["status"].selection)[self.status],
            "output": self.output or {},
            "model": self.model_used or "",
            "created_at": fields.Datetime.to_string(self.create_date),
            "reviewed_by": self.reviewed_by_id.name or "",
        }


class CareosAi(models.AbstractModel):
    _name = "careos.ai"
    _description = "CareOS Intelligence"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @api.model
    def _careos_config(self):
        params = self.env["ir.config_parameter"].sudo()
        return {
            "enabled": params.get_param("careos_ai.enabled") in ("1", "True", "true"),
            "api_key": params.get_param("careos_ai.api_key") or None,
        }

    @api.model
    def careos_status(self):
        config = self._careos_config()
        roles = set(self.env.user._careos_role_keys())
        return {
            "enabled": config["enabled"],
            "can_use": self.env.su or bool(ASSIST_ROLES & roles),
            "is_admin": "admin" in roles or self.env.user.has_group("base.group_system"),
        }

    @api.model
    def careos_configure(self, enabled, api_key=None):
        """Administrators switch CareOS Intelligence on and may store an API key
        (otherwise the SDK uses the server's ANTHROPIC_API_KEY / credentials)."""
        if not self.env.user.has_group("careos_base.group_careos_admin") and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can configure CareOS Intelligence."))
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("careos_ai.enabled", "1" if enabled else "0")
        if api_key is not None:
            params.set_param("careos_ai.api_key", api_key.strip() or False)
        return self.careos_status()

    # ------------------------------------------------------------------
    # De-identified context (built with the caller's own access rights)
    # ------------------------------------------------------------------

    @api.model
    def _careos_context(self, kind, res_id):
        if kind == "patient":
            patient = self.env["careos.patient"].browse(res_id)
            profile = patient.careos_get_profile()
            data = {
                "age": profile.get("age"), "sex": profile.get("sex_label"),
                "allergies": [f"{a['allergen']} ({a['severity_label']}) {a['reaction']}".strip() for a in profile["allergies"]],
                "conditions": [f"{c['name']} {c['code']} — {c['status_label']}" for c in profile.get("conditions", [])],
                "current_medications": [f"{m['med']} {m['dose']} {m['freq']}" for m in profile.get("current_medications", [])],
                "timeline": [f"{e['date'][:10]} {e['title']}: {e['detail']}" for e in profile["timeline"][:20]
                             if e.get("kind") != "registration"],
            }
            if profile.get("lab_access"):
                labs = patient.careos_get_lab_results()[:5]
                data["recent_lab_results"] = [
                    {"tests": o["tests"], "status": o["state_label"],
                     "values": [f"{r['name']} {r['value']} {r['unit']} ({r['flag'] or 'no flag'})" for r in o.get("results") or []]}
                    for o in labs]
            return "careos.patient", data
        if kind == "encounter":
            enc = self.env["careos.encounter"].browse(res_id).careos_get_workspace()
            if not enc["can_edit_clinical"]:
                raise AccessError(_("Note structuring is available to the treating doctor on an open encounter."))
            return "careos.encounter", {
                "visit_type": enc["type"], "reason": enc["appointment"]["reason"],
                "age": enc["patient_context"]["age"], "sex": enc["patient_context"]["sex"],
                "vitals": {v["label"]: f"{v['value']} {v['unit']}".strip() for v in enc["vitals"] if v["value"]},
                "chief_complaint": enc["chief_complaint"], "clinical_notes": enc["notes"], "plan": enc["plan"],
                "recorded_diagnoses": [f"{d['description']} {d['code']}" for d in enc["diagnoses"]],
            }
        if kind == "reception":
            d = self.env["careos.appointment"].careos_reception_dashboard()
            return "careos.branch", {
                "kpis": {k["label"]: k["value"] for k in d["kpis"]},
                "appointments": [{"time": a["start"][11:16], "type": a["type"]["name"], "status": a["state_label"]}
                                 for a in d["appointments"]],
                "waiting": [{"ticket": t["label"], "checked_in_at": t["checked_in_at"][11:16], "status": t["state_label"]}
                            for t in (d.get("queue") or {}).get("waiting", [])],
                "now_utc": fields.Datetime.to_string(fields.Datetime.now())[11:16],
            }
        if kind == "manager":
            d = self.env["careos.analytics"].careos_manager_dashboard()
            return "careos.branch", {
                "kpis": {k["label"]: f"{k['value']} ({k['delta']['text']})" for k in d["kpis"]},
                "alert": d["alert"] and d["alert"]["text"],
                "revenue_by_department": {r["name"]: r["label"] for r in d["dept_revenue"]},
                "doctor_utilization": [r["label"] for r in d["utilization"]],
            }
        if kind == "invoice":
            inv = self.env["careos.billing"].careos_invoice_detail(res_id)
            return "account.move", {
                "status": inv["status_label"], "total": inv["total"], "paid": inv["paid"], "balance": inv["balance"],
                "currency": inv["currency"], "due": inv["due"],
                "lines": [f"{line['service']} × {line['qty']} = {line['total']}" for line in inv["lines"]],
                "payments": [f"{p['date']} {p['method']} {p['amount']}" for p in inv["payments"]],
            }
        raise UserError(_("CareOS Intelligence is not available here."))

    @api.model
    def _careos_patient_for(self, kind, res_id):
        if kind == "patient":
            return self.env["careos.patient"].sudo().browse(res_id)
        if kind == "encounter":
            return self.env["careos.encounter"].sudo().browse(res_id).patient_id
        if kind == "invoice":
            return self.env["account.move"].sudo().browse(res_id).careos_patient_id
        return self.env["careos.patient"]

    @api.model
    def _careos_scrub(self, context, patient):
        """Replace the patient's identifiers wherever they appear in the
        context (free text included) before anything leaves CareOS."""
        if not patient:
            return context
        identifiers = [patient.name, patient.ref, patient.phone, patient.national_id, patient.email]
        identifiers += (patient.name or "").split()
        identifiers = sorted({i for i in identifiers if i and len(i) >= 3}, key=len, reverse=True)
        text = json.dumps(context, default=str, ensure_ascii=False)
        for identifier in identifiers:
            text = text.replace(identifier, "[patient]")
        return json.loads(text)

    # ------------------------------------------------------------------
    # Provider call
    # ------------------------------------------------------------------

    @api.model
    def _careos_call_model(self, kind, context):
        """Ask Claude for the task's structured output. Returns (output, model, request_id)."""
        import anthropic  # declared external dependency; imported lazily so the module loads without it

        config = self._careos_config()
        instruction, schema = TASKS[kind]
        client = anthropic.Anthropic(api_key=config["api_key"]) if config["api_key"] else anthropic.Anthropic()
        try:
            response = client.beta.messages.create(
                model=MODEL,
                max_tokens=8000,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"{instruction}\n\n<record>\n{json.dumps(context, default=str, indent=1)}\n</record>"}],
            )
        except anthropic.AuthenticationError:
            raise UserError(_("CareOS Intelligence could not authenticate. Ask an administrator to check the API key."))
        except anthropic.RateLimitError:
            raise UserError(_("CareOS Intelligence is busy. Try again in a minute."))
        except anthropic.APIConnectionError:
            raise UserError(_("CareOS Intelligence is unreachable from this server."))
        except anthropic.APIStatusError as error:
            _logger.warning("CareOS AI request failed: %s", error)
            raise UserError(_("CareOS Intelligence returned an error (%s).", error.status_code))
        if response.stop_reason == "refusal":
            raise UserError(_("CareOS Intelligence declined this request."))
        text = next((block.text for block in response.content if block.type == "text"), "")
        try:
            output = json.loads(text)
        except ValueError:
            raise UserError(_("CareOS Intelligence returned an unreadable answer. Try again."))
        return output, response.model, getattr(response, "_request_id", None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def careos_assist(self, kind, res_id=0):
        status = self.careos_status()
        if not status["can_use"]:
            raise AccessError(_("Your role does not have access to CareOS Intelligence."))
        if not status["enabled"]:
            raise UserError(_("CareOS Intelligence is not enabled. An administrator can enable it in CareOS settings."))
        if kind not in TASKS:
            raise UserError(_("CareOS Intelligence is not available here."))
        res_model, context = self._careos_context(kind, res_id)
        context = self._careos_scrub(context, self._careos_patient_for(kind, res_id))
        output, model_used, request_id = self._careos_call_model(kind, context)
        suggestion = self.env["careos.ai.suggestion"].sudo().create({
            "kind": kind, "res_model": res_model, "res_id": res_id or 0, "user_id": self.env.uid,
            "output": output, "model_used": model_used, "request_id": request_id,
        })
        return suggestion._careos_payload()

    @api.model
    def careos_apply_note(self, suggestion_id, fields_to_apply):
        """Doctor copies reviewed parts of a note structuring into the chart.
        Only the listed fields are written, through the encounter's normal
        permission checks; diagnoses are never added automatically."""
        suggestion = self.env["careos.ai.suggestion"].sudo().browse(suggestion_id)
        if not suggestion.exists() or suggestion.kind != "encounter" or suggestion.user_id != self.env.user:
            raise AccessError(_("Suggestion not found."))
        if suggestion.status != "generated":
            raise UserError(_("This suggestion was already reviewed."))
        output = suggestion.output or {}
        mapping = {"chief_complaint": "chief_complaint", "plan": "plan", "assessment": "notes"}
        vals = {mapping[key]: output.get(key) for key in fields_to_apply if key in mapping and output.get(key)}
        if not vals:
            raise UserError(_("Choose at least one section to apply."))
        encounter = self.env["careos.encounter"].browse(suggestion.res_id)
        if "notes" in vals and encounter.notes:
            vals["notes"] = f"{encounter.notes}\n\nAssessment: {vals['notes']}"
        encounter.careos_save(vals)
        suggestion.write({"status": "applied", "reviewed_by_id": self.env.uid, "reviewed_at": fields.Datetime.now()})
        encounter.message_post(body=_("AI-structured note reviewed and applied by %s (%s).", self.env.user.name, ", ".join(vals)))
        return suggestion._careos_payload()

    @api.model
    def careos_dismiss(self, suggestion_id):
        suggestion = self.env["careos.ai.suggestion"].sudo().browse(suggestion_id)
        if suggestion.user_id != self.env.user:
            raise AccessError(_("Suggestion not found."))
        suggestion.write({"status": "dismissed", "reviewed_by_id": self.env.uid, "reviewed_at": fields.Datetime.now()})
        return suggestion._careos_payload()
