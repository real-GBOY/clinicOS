from odoo import fields, models


class CareosPatientContact(models.Model):
    """A related person: next of kin, guardian or emergency contact."""

    _name = "careos.patient.contact"
    _description = "Patient Contact"
    _order = "is_emergency desc, sequence, id"

    patient_id = fields.Many2one("careos.patient", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="patient_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    relationship = fields.Selection(
        [
            ("spouse", "Spouse"),
            ("parent", "Parent"),
            ("child", "Child"),
            ("sibling", "Sibling"),
            ("guardian", "Guardian"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    phone = fields.Char(required=True)
    is_emergency = fields.Boolean(string="Emergency contact", default=True)

    def _careos_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "relationship": dict(self._fields["relationship"].selection).get(self.relationship, ""),
            "phone": self.phone,
            "is_emergency": self.is_emergency,
        }
