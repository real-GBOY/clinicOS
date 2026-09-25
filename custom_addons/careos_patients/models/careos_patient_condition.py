from odoo import api, fields, models


class CareosPatientCondition(models.Model):
    """A chronic or significant condition on the problem list. Clinical data:
    only clinical roles can read or edit it."""

    _name = "careos.patient.condition"
    _description = "Patient Condition"
    _inherit = ["mail.thread"]
    _order = "status, onset_date desc, id desc"

    patient_id = fields.Many2one("careos.patient", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="patient_id.company_id", store=True, index=True)
    name = fields.Char(string="Condition", required=True, tracking=True)
    code = fields.Char(help="ICD-10 style code, e.g. I10.", tracking=True)
    status = fields.Selection(
        [("active", "Active"), ("controlled", "Controlled"), ("resolved", "Resolved")],
        required=True,
        default="active",
        tracking=True,
    )
    onset_date = fields.Date(tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
        return super().create(vals_list)

    def _careos_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code or "",
            "status": self.status,
            "status_label": dict(self._fields["status"].selection).get(self.status, ""),
            "onset_date": self.onset_date and fields.Date.to_string(self.onset_date),
        }
