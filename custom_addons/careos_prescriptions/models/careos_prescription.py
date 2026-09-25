from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

STATES = [
    ("draft", "Draft"),
    ("issued", "Issued"),
    ("dispensed", "Dispensed"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]
# Spec §6: Draft → Issued → Dispensed → Completed · Issued → Cancelled.
# (A draft can also be discarded, i.e. cancelled, before issue.)
TRANSITIONS = {
    "issue": ({"draft"}, "issued", {"doctor"}),
    "dispense": ({"issued"}, "dispensed", {"pharmacy"}),
    "complete": ({"dispensed"}, "completed", {"doctor", "pharmacy"}),
    "cancel": ({"draft", "issued"}, "cancelled", {"doctor"}),
}
STATE_TIMESTAMP = {"issued": "issued_at", "dispensed": "dispensed_at", "completed": "completed_at", "cancelled": "cancelled_at"}


class CareosPrescription(models.Model):
    _name = "careos.prescription"
    _description = "Prescription"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"
    _rec_names_search = ["name", "patient_id.name", "patient_id.ref"]

    name = fields.Char(required=True, readonly=True, copy=False, index=True, default=lambda self: _("New"))
    encounter_id = fields.Many2one("careos.encounter", required=True, readonly=True, index=True, ondelete="restrict")
    patient_id = fields.Many2one(related="encounter_id.patient_id", store=True, index=True)
    provider_id = fields.Many2one(related="encounter_id.provider_id", store=True, index=True, string="Prescriber")
    branch_id = fields.Many2one(related="encounter_id.branch_id", store=True, index=True)
    company_id = fields.Many2one(related="encounter_id.company_id", store=True, index=True)
    state = fields.Selection(STATES, required=True, default="draft", index=True, tracking=True)
    line_ids = fields.One2many("careos.prescription.line", "prescription_id", string="Medications")
    notes = fields.Text()
    issued_at = fields.Datetime(readonly=True)
    dispensed_at = fields.Datetime(readonly=True)
    dispensed_by_id = fields.Many2one("res.users", readonly=True)
    picking_id = fields.Many2one("stock.picking", readonly=True, string="Stock issue")
    completed_at = fields.Datetime(readonly=True)
    cancelled_at = fields.Datetime(readonly=True)

    def _compute_display_name(self):
        for rx in self:
            rx.display_name = f"{rx.name} · {rx.patient_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("careos.prescription") or _("New")
        prescriptions = super().create(vals_list)
        prescriptions._check_prescriber()
        return prescriptions

    def write(self, vals):
        if "state" in vals and not self.env.context.get("careos_rx_internal"):
            raise UserError(_("Prescription status changes only through its workflow."))
        return super().write(vals)

    def _check_prescriber(self):
        if self.env.su:
            return
        if "doctor" not in self.env.user._careos_role_keys():
            raise AccessError(_("Only doctors can prescribe."))
        for rx in self:
            if rx.encounter_id.state != "open":
                raise UserError(_("Prescriptions can only be written during an open encounter."))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _careos_transition(self, action, extra=None):
        sources, target, roles = TRANSITIONS[action]
        if not self.env.su and not roles & set(self.env.user._careos_role_keys()):
            raise AccessError(_("Your role cannot %s prescriptions.", action))
        self.check_access("write")
        for rx in self:
            if rx.state not in sources:
                raise UserError(_("%(ref)s is %(state)s.", ref=rx.name, state=dict(STATES)[rx.state]))
        self.with_context(careos_rx_internal=True).write({"state": target, STATE_TIMESTAMP[target]: fields.Datetime.now(), **(extra or {})})
        return True

    def action_issue(self):
        for rx in self:
            if not rx.line_ids:
                raise UserError(_("Add at least one medication before issuing."))
        self._careos_transition("issue")
        Notification = self.env["careos.notification"]
        for rx in self:
            Notification._careos_notify(
                Notification._careos_users_with_roles(["pharmacy"], rx.branch_id),
                _("Prescription to dispense — %s", rx.patient_id.name),
                body=", ".join(rx.line_ids.mapped("product_id.name")), kind="info",
                screen="prescription", res_id=rx.id,
            )
        return True

    def action_dispense(self):
        """Pharmacy hands over the medicines: stock leaves the branch store in
        the same transaction as the status change."""
        roles = set(self.env.user._careos_role_keys())
        if not self.env.su and "pharmacy" not in roles:
            raise AccessError(_("Only pharmacists dispense prescriptions."))
        for rx in self:
            if rx.state != "issued":
                raise UserError(_("%(ref)s is %(state)s.", ref=rx.name, state=dict(STATES)[rx.state]))
            picking = self.env["careos.inventory"]._careos_consume(
                rx.branch_id, [(line.product_id, line.quantity) for line in rx.line_ids], rx.name,
            )
            rx._careos_transition("dispense", {"dispensed_by_id": self.env.uid, "picking_id": picking.id})
        return True

    def action_complete(self):
        return self._careos_transition("complete")

    def action_cancel(self):
        return self._careos_transition("cancel")

    @api.model
    def _careos_cron_complete_courses(self):
        """Mark dispensed prescriptions completed once the longest course has ended."""
        today = fields.Date.context_today(self)
        for rx in self.search([("state", "=", "dispensed")]):
            longest = max(rx.line_ids.mapped("duration_days") or [0])
            if rx.dispensed_at and rx.dispensed_at.date() + timedelta(days=longest) < today:
                rx.sudo()._careos_transition("complete")

    # ------------------------------------------------------------------
    # Safety and payloads
    # ------------------------------------------------------------------

    def _careos_allergy_warnings(self):
        """Medication names that mention one of the patient's allergens."""
        self.ensure_one()
        allergens = [a.allergen.lower() for a in self.patient_id.allergy_ids.filtered("active")]
        warnings = []
        for line in self.line_ids:
            name = (line.product_id.name or "").lower()
            hits = [a for a in allergens if a and (a in name or name.split(" ")[0] in a)]
            if hits:
                warnings.append(_("%(med)s: patient is allergic to %(allergen)s",
                                  med=line.product_id.name, allergen=", ".join(hits)))
        return warnings

    def _careos_payload(self):
        self.ensure_one()
        roles = set(self.env.user._careos_role_keys())
        is_su = self.env.su
        actions = []
        can_write = self.has_access("write")
        for action, (sources, _target, action_roles) in TRANSITIONS.items():
            if self.state in sources and can_write and (is_su or action_roles & roles):
                actions.append(action)
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": dict(STATES)[self.state],
            "patient": {"id": self.patient_id.id, "name": self.patient_id.name, "ref": self.patient_id.ref},
            "provider": {"id": self.provider_id.id, "name": self.provider_id.name},
            # Visit date via sudo: pharmacists see prescriptions, not encounters.
            "encounter": {"id": self.encounter_id.id, "date": fields.Datetime.to_string(self.sudo().encounter_id.appointment_id.start)},
            "lines": [line._careos_payload() for line in self.line_ids],
            "notes": self.notes or "",
            "issued_at": self.issued_at and fields.Datetime.to_string(self.issued_at),
            "dispensed_at": self.dispensed_at and fields.Datetime.to_string(self.dispensed_at),
            "dispensed_by": self.dispensed_by_id.name or "",
            "allergy_warnings": self._careos_allergy_warnings(),
            "actions": actions,
            "can_edit_lines": self.state == "draft" and can_write and (is_su or "doctor" in roles),
        }

    def careos_get_detail(self):
        self.ensure_one()
        self.check_access("read")
        return self._careos_payload()

    @api.model
    def careos_list(self, state=None, query=None, limit=100):
        domain = []
        if state:
            domain.append(("state", "=", state))
        if (query or "").strip():
            domain.append(("display_name", "ilike", query.strip()))
        branch = self.env.user.careos_branch_id
        if branch:
            domain.append(("branch_id", "=", branch.id))
        return [rx._careos_payload() for rx in self.search(domain, limit=limit)]

    @api.model
    def careos_medications(self):
        """Medication catalogue for the prescription line picker."""
        products = self.env["product.product"].sudo().search([("careos_item_type", "=", "medication")], order="name")
        return [{"id": p.id, "name": p.display_name, "strength": p.careos_strength or ""} for p in products]

    def _careos_search_result(self):
        self.ensure_one()
        return {
            "id": self.id,
            "title": f"{self.name} · {self.patient_id.name}",
            "detail": f"{', '.join(self.line_ids.mapped('product_id.name'))} · {dict(STATES)[self.state]}",
        }


class CareosPrescriptionLine(models.Model):
    _name = "careos.prescription.line"
    _description = "Prescription Line"
    _order = "id"

    prescription_id = fields.Many2one("careos.prescription", required=True, index=True, ondelete="cascade")
    patient_id = fields.Many2one(related="prescription_id.patient_id", store=True, index=True)
    company_id = fields.Many2one(related="prescription_id.company_id", store=True, index=True)
    state = fields.Selection(related="prescription_id.state", store=True)
    product_id = fields.Many2one("product.product", string="Medication", required=True,
                                 domain=[("careos_item_type", "=", "medication")])
    dose = fields.Char(required=True, help="e.g. 10mg")
    frequency = fields.Char(required=True, help="e.g. Once daily")
    duration_days = fields.Integer(string="Duration (days)", required=True, default=30)
    quantity = fields.Float(string="Packs to dispense", required=True, default=1.0)
    instructions = fields.Char(help="e.g. Take in the morning")

    @api.constrains("duration_days", "quantity")
    def _check_amounts(self):
        for line in self:
            if line.duration_days <= 0 or line.duration_days > 365:
                raise ValidationError(_("Duration must be between 1 and 365 days."))
            if line.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_editable()
        return lines

    def write(self, vals):
        self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()

    def _check_editable(self):
        if self.env.su:
            return
        if "doctor" not in self.env.user._careos_role_keys():
            raise AccessError(_("Only doctors can change prescriptions."))
        if self.prescription_id.filtered(lambda rx: rx.state != "draft"):
            raise UserError(_("An issued prescription cannot be changed. Cancel it and write a new one."))

    def _careos_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "product": {"id": self.product_id.id, "name": self.product_id.display_name},
            "med": self.product_id.name,
            "dose": self.dose,
            "freq": self.frequency,
            "duration": _("%s days", self.duration_days),
            "duration_days": self.duration_days,
            "quantity": self.quantity,
            "instructions": self.instructions or "",
            "status": dict(STATES)[self.prescription_id.state],
            "state": self.prescription_id.state,
        }
