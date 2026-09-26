from odoo import api, models


class CareosPrescription(models.Model):
    _inherit = "careos.prescription"

    @api.model
    def _careos_demo_prescriptions(self):
        """Synthetic prescriptions for today's demo visits."""
        def product(index):
            return self.env.ref(f"careos_demo.demo_item_{index}")

        def encounter_for(patient_xmlid):
            patient = self.env.ref(f"careos_patients.{patient_xmlid}")
            return self.env["careos.encounter"].search([("patient_id", "=", patient.id)], limit=1)

        mona = encounter_for("patient_mona_youssef")
        if mona:
            rx = self.create({"encounter_id": mona.id, "line_ids": [(0, 0, {
                "product_id": product(4).id, "dose": "5mg", "frequency": "Once daily", "duration_days": 30,
                "quantity": 1, "instructions": "Take in the morning"})]})
            rx.action_issue()
            rx.action_dispense()
        karim = encounter_for("patient_karim_adel")
        if karim:
            rx = self.create({"encounter_id": karim.id, "line_ids": [
                (0, 0, {"product_id": product(3).id, "dose": "75mg", "frequency": "Once daily", "duration_days": 30,
                        "quantity": 1, "instructions": "After breakfast"}),
                (0, 0, {"product_id": product(1).id, "dose": "20mg", "frequency": "Once daily, evening", "duration_days": 30,
                        "quantity": 1, "instructions": "With food"}),
            ]})
            rx.action_issue()
