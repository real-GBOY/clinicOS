from odoo import api, fields, models


class CareosPatientAllergy(models.Model):
    """A recorded allergy. Readable by all staff because it is safety-critical
    (reception, pharmacy and lab all need to see it); only clinical roles may
    record or change allergies. Entries are deactivated, never deleted, so the
    history of what was recorded is kept."""

    _name = "careos.patient.allergy"
    _description = "Patient Allergy"
    _inherit = ["mail.thread"]
    _order = "severity_rank desc, allergen"

    patient_id = fields.Many2one("careos.patient", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="patient_id.company_id", store=True, index=True)
    allergen = fields.Char(required=True, tracking=True)
    severity = fields.Selection(
        [("mild", "Mild"), ("moderate", "Moderate"), ("severe", "Severe")],
        required=True,
        default="moderate",
        tracking=True,
    )
    severity_rank = fields.Integer(compute="_compute_severity_rank", store=True)
    reaction = fields.Char(tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    @api.depends("severity")
    def _compute_severity_rank(self):
        ranks = {"mild": 1, "moderate": 2, "severe": 3}
        for allergy in self:
            allergy.severity_rank = ranks.get(allergy.severity, 0)

    def _careos_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "allergen": self.allergen,
            "severity": self.severity,
            "severity_label": dict(self._fields["severity"].selection).get(self.severity, ""),
            "reaction": self.reaction or "",
        }
