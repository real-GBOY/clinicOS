from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.careos_base.models.authorization import has_role, require_role

STATES = [("open", "In progress"), ("done", "Completed")]

VITAL_FIELDS = (
    "bp_systolic", "bp_diastolic", "heart_rate", "temperature", "weight", "height", "spo2", "respiratory_rate",
)
FOLLOW_UP_ROLES = {"reception", "doctor", "nurse", "manager"}
CLINICAL_FIELDS = ("chief_complaint", "notes", "plan", "follow_up_date", "follow_up_reason")

# Plausibility limits: values outside are almost certainly entry errors.
VITAL_LIMITS = {
    "bp_systolic": (50, 260, "mmHg"),
    "bp_diastolic": (30, 160, "mmHg"),
    "heart_rate": (20, 250, "bpm"),
    "temperature": (30.0, 44.0, "°C"),
    "weight": (0.5, 400.0, "kg"),
    "height": (30.0, 250.0, "cm"),
    "spo2": (50, 100, "%"),
    "respiratory_rate": (4, 60, "/min"),
}


class CareosEncounter(models.Model):
    """The clinical record of one visit (spec: Appointment → Encounter 1:1,
    created at check-in so vitals can be taken while the patient waits).

    The doctor documents and signs off (Complete encounter); the front desk's
    appointment completion only closes the visit operationally.
    """

    _name = "careos.encounter"
    _description = "Clinical Encounter"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, readonly=True, copy=False, index=True, default=lambda self: _("New"))
    appointment_id = fields.Many2one("careos.appointment", required=True, readonly=True, index=True, ondelete="restrict")
    patient_id = fields.Many2one(related="appointment_id.patient_id", store=True, index=True)
    provider_id = fields.Many2one(related="appointment_id.provider_id", store=True, index=True)
    branch_id = fields.Many2one(related="appointment_id.branch_id", store=True, index=True)
    company_id = fields.Many2one(related="appointment_id.company_id", store=True, index=True)
    state = fields.Selection(STATES, required=True, default="open", index=True, tracking=True)

    # Vitals
    bp_systolic = fields.Integer(string="Systolic BP", tracking=True)
    bp_diastolic = fields.Integer(string="Diastolic BP", tracking=True)
    heart_rate = fields.Integer(tracking=True)
    temperature = fields.Float(digits=(4, 1), tracking=True)
    weight = fields.Float(digits=(5, 1), tracking=True)
    height = fields.Float(digits=(5, 1), tracking=True)
    spo2 = fields.Integer(string="SpO2", tracking=True)
    respiratory_rate = fields.Integer(tracking=True)
    bmi = fields.Float(string="BMI", digits=(4, 1), compute="_compute_bmi", store=True)
    vitals_recorded_at = fields.Datetime(readonly=True)
    vitals_recorded_by_id = fields.Many2one("res.users", readonly=True)

    # Documentation
    chief_complaint = fields.Text(tracking=True)
    notes = fields.Text(string="Clinical notes", tracking=True)
    plan = fields.Text(tracking=True)
    diagnosis_ids = fields.One2many("careos.diagnosis", "encounter_id", string="Diagnoses")
    follow_up_date = fields.Date(tracking=True)
    follow_up_reason = fields.Char(tracking=True)

    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    completed_by_id = fields.Many2one("res.users", readonly=True)

    _appointment_uniq = models.Constraint("UNIQUE(appointment_id)", "An appointment has one encounter.")

    @api.depends("weight", "height")
    def _compute_bmi(self):
        for encounter in self:
            height_m = encounter.height / 100 if encounter.height else 0
            encounter.bmi = round(encounter.weight / (height_m * height_m), 1) if encounter.weight and height_m else 0

    @api.constrains(*VITAL_FIELDS)
    def _check_vitals(self):
        for encounter in self:
            for field_name, (low, high, unit) in VITAL_LIMITS.items():
                value = encounter[field_name]
                if value and not low <= value <= high:
                    label = encounter._fields[field_name].string
                    raise ValidationError(_("%(label)s must be between %(low)s and %(high)s %(unit)s.",
                                            label=label, low=low, high=high, unit=unit))
            if encounter.bp_systolic and encounter.bp_diastolic and encounter.bp_diastolic >= encounter.bp_systolic:
                raise ValidationError(_("Diastolic pressure must be lower than systolic pressure."))

    @api.constrains("follow_up_date")
    def _check_follow_up(self):
        for encounter in self:
            if encounter.follow_up_date and encounter.follow_up_date < fields.Date.context_today(encounter):
                raise ValidationError(_("The follow-up date cannot be in the past."))

    def _compute_display_name(self):
        for encounter in self:
            encounter.display_name = f"{encounter.name} · {encounter.patient_id.name}"

    # ------------------------------------------------------------------
    # ORM guards
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("careos.encounter") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if self.env.su or self.env.context.get("careos_encounter_internal"):
            return super().write(vals)
        if "state" in vals:
            raise UserError(_("Use Complete encounter to sign off."))
        if self.filtered(lambda e: e.state == "done"):
            raise UserError(_("A completed encounter cannot be changed."))
        if not has_role(self.env, "doctor"):
            # Nurses may record vitals only.
            if not has_role(self.env, "nurse") or set(vals) - set(VITAL_FIELDS):
                raise AccessError(_("Only the treating doctor can edit the clinical record."))
        if set(vals) & set(VITAL_FIELDS):
            vals = {**vals, "vitals_recorded_at": fields.Datetime.now(), "vitals_recorded_by_id": self.env.uid}
        return super().write(vals)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def action_complete(self):
        """Doctor sign-off. Requires a diagnosis; closes the appointment if
        the patient is still in consultation."""
        require_role(self.env, "doctor", _("Only a doctor can complete an encounter."))
        self.check_access("write")
        for encounter in self:
            if encounter.state == "done":
                raise UserError(_("%s is already completed.", encounter.name))
            if not encounter.diagnosis_ids:
                raise UserError(_("Record at least one diagnosis before completing the encounter."))
        self.with_context(careos_encounter_internal=True).write({
            "state": "done", "completed_at": fields.Datetime.now(), "completed_by_id": self.env.uid,
        })
        for encounter in self:
            if encounter.appointment_id.state == "in_progress":
                encounter.appointment_id.action_complete()
        return True

    # ------------------------------------------------------------------
    # Payloads
    # ------------------------------------------------------------------

    def _careos_vitals(self):
        self.ensure_one()
        bp = f"{self.bp_systolic}/{self.bp_diastolic}" if self.bp_systolic and self.bp_diastolic else ""
        return [
            {"key": "bp", "label": _("Blood pressure"), "value": bp, "unit": "mmHg"},
            {"key": "heart_rate", "label": _("Heart rate"), "value": self.heart_rate or "", "unit": "bpm"},
            {"key": "temperature", "label": _("Temperature"), "value": self.temperature or "", "unit": "°C"},
            {"key": "weight", "label": _("Weight"), "value": self.weight or "", "unit": "kg"},
            {"key": "spo2", "label": _("SpO2"), "value": self.spo2 or "", "unit": "%"},
            {"key": "bmi", "label": _("BMI"), "value": self.bmi or "", "unit": ""},
        ]

    def _careos_summary_payload(self):
        self.ensure_one()
        to_str = fields.Datetime.to_string
        primary = self.diagnosis_ids.sorted(lambda d: not d.is_primary)[:1]
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": dict(STATES)[self.state],
            "date": to_str(self.appointment_id.start),
            "patient": {"id": self.patient_id.id, "name": self.patient_id.name, "ref": self.patient_id.ref},
            "provider": {"id": self.provider_id.id, "name": self.provider_id.name},
            "type": self.appointment_id.type_id.name,
            "diagnosis": f"{primary.description} ({primary.code})" if primary.code else (primary.description or ""),
            "appointment_state": self.appointment_id.state,
            "completed_at": self.completed_at and to_str(self.completed_at),
        }

    def careos_get_workspace(self):
        """Everything the encounter screen needs in one call."""
        self.ensure_one()
        self.check_access("read")
        patient = self.patient_id
        is_doctor = has_role(self.env, "doctor")
        can_write = self.state == "open" and self.has_access("write")
        previous = self.search([("patient_id", "=", patient.id), ("id", "!=", self.id), ("state", "=", "done")], limit=5)
        payload = {
            **self._careos_summary_payload(),
            "appointment": {"id": self.appointment_id.id, "name": self.appointment_id.name,
                            "reason": self.appointment_id.reason or "", "start": fields.Datetime.to_string(self.appointment_id.start)},
            "vitals": self._careos_vitals(),
            "vitals_raw": {f: self[f] or False for f in VITAL_FIELDS},
            "vitals_recorded_at": self.vitals_recorded_at and fields.Datetime.to_string(self.vitals_recorded_at),
            "chief_complaint": self.chief_complaint or "",
            "notes": self.notes or "",
            "plan": self.plan or "",
            "follow_up_date": self.follow_up_date and fields.Date.to_string(self.follow_up_date),
            "follow_up_reason": self.follow_up_reason or "",
            "diagnoses": [d._careos_payload() for d in self.diagnosis_ids],
            "patient_context": {
                "age": patient.age if patient.date_of_birth else None,
                "sex": dict(patient._fields["sex"].selection).get(patient.sex, ""),
                "allergies": [a._careos_payload() for a in patient.allergy_ids.filtered("active")],
                "conditions": [c._careos_payload() for c in patient.condition_ids.filtered("active")]
                if self.env.user.has_group("careos_base.group_careos_clinical") else [],
            },
            "previous_encounters": [e._careos_summary_payload() for e in previous],
            "can_edit_clinical": can_write and is_doctor,
            "can_edit_vitals": can_write,
            "can_complete": self.state == "open" and is_doctor and self.has_access("write"),
            "completed_by": self.completed_by_id.name or "",
        }
        return self._careos_extend_workspace(payload)

    def _careos_extend_workspace(self, payload):
        """Hook: prescriptions/lab add their sections."""
        return payload

    def careos_save(self, vals):
        """Save documentation/vitals from the encounter screen."""
        self.ensure_one()
        allowed = set(VITAL_FIELDS) | set(CLINICAL_FIELDS)
        self.write({k: (v if v not in ("", None) else False) for k, v in vals.items() if k in allowed})
        return self.careos_get_workspace()

    @api.model
    def careos_list(self, filters=None, limit=100):
        filters = filters or {}
        domain = []
        if filters.get("state"):
            domain.append(("state", "=", filters["state"]))
        if filters.get("unsigned"):
            domain += [("state", "=", "open"), ("appointment_id.state", "in", ("done", "no_show"))]
        if (filters.get("query") or "").strip():
            domain.append(("display_name", "ilike", filters["query"].strip()))
        branch = self.env.user.careos_branch_id
        if branch:
            domain.append(("branch_id", "=", branch.id))
        encounters = self.search(domain, limit=limit)
        return [e._careos_summary_payload() for e in encounters]

    @api.model
    def careos_follow_ups(self, days=7):
        """Follow-ups due within ``days`` (or overdue) with no future booking
        for the patient. Front desk sees patient, due date and reason only."""
        require_role(self.env, FOLLOW_UP_ROLES, _("You do not have access to follow-ups."))
        today = fields.Date.context_today(self)
        domain = [("follow_up_date", "!=", False), ("follow_up_date", "<=", today + timedelta(days=days))]
        branch = self.env.user.careos_branch_id
        if branch:
            domain.append(("branch_id", "=", branch.id))
        # Doctors see their own follow-ups through record rules; the front desk and
        # managers see the branch list (patient, due date and reason only).
        Encounter = self.sudo() if has_role(self.env, {"reception", "manager"}) or not has_role(self.env, "doctor") else self
        encounters = Encounter.search(domain, order="follow_up_date")
        booked_patients = self.env["careos.appointment"].sudo().search([
            ("patient_id", "in", encounters.patient_id.ids),
            ("state", "in", ("draft", "confirmed")),
            ("start", ">=", fields.Datetime.now()),
        ]).patient_id
        rows = []
        for encounter in encounters:
            if encounter.patient_id in booked_patients:
                continue
            rows.append({
                "encounter_id": encounter.id,
                "patient": {"id": encounter.patient_id.id, "name": encounter.patient_id.name},
                "provider": {"id": encounter.provider_id.id, "name": encounter.provider_id.name},
                "due": fields.Date.to_string(encounter.follow_up_date),
                "overdue": encounter.follow_up_date < today,
                "reason": encounter.follow_up_reason or "",
            })
        return rows
