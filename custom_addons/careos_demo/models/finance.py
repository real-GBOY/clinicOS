from odoo import api, models


class CareosBilling(models.AbstractModel):
    _inherit = "careos.billing"

    @api.model
    def _careos_demo_billing(self):
        """Bill today's completed demo visit and take a part payment."""
        mona = self.env.ref("careos_patients.patient_mona_youssef")
        appointment = self.env["careos.appointment"].search([("patient_id", "=", mona.id), ("state", "=", "done")], limit=1)
        if appointment:
            move_id = self.careos_create_invoice(appointment.id)
            self.careos_post(move_id)
            self.careos_register_payment(move_id, 400.0, "card")
