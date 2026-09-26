from odoo import api, models


class CareosPortalDemo(models.AbstractModel):
    _inherit = "careos.portal"

    @api.model
    def _careos_demo_portal(self):
        """Demo portal login for Ahmed Hassan: login ``patient``, password
        ``patient`` (demo databases only)."""
        patient = self.env.ref("careos_patients.patient_ahmed_hassan")
        partner = patient._careos_partner()
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "login": "patient", "password": "patient", "partner_id": partner.id,
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        patient.portal_user_id = user
