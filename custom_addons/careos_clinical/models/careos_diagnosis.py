from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class CareosDiagnosis(models.Model):
    """A diagnosis recorded in an encounter. ICD-10-style code field; a full
    terminology service is out of scope (spec §14.3)."""

    _name = "careos.diagnosis"
    _description = "Diagnosis"
    _order = "is_primary desc, id"

    encounter_id = fields.Many2one("careos.encounter", required=True, index=True, ondelete="cascade")
    patient_id = fields.Many2one(related="encounter_id.patient_id", store=True, index=True)
    company_id = fields.Many2one(related="encounter_id.company_id", store=True, index=True)
    code = fields.Char(help="ICD-10 style code, e.g. I10.")
    description = fields.Char(required=True)
    is_primary = fields.Boolean(string="Primary")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
        records = super().create(vals_list)
        records._check_editable()
        return records

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
            raise AccessError(_("Only a doctor can record diagnoses."))
        if self.encounter_id.filtered(lambda e: e.state == "done"):
            raise UserError(_("A completed encounter cannot be changed."))

    def _careos_payload(self):
        self.ensure_one()
        return {"id": self.id, "code": self.code or "", "description": self.description, "is_primary": self.is_primary}
