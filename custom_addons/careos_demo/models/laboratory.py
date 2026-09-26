from odoo import api, models


class CareosLabOrder(models.Model):
    _inherit = "careos.lab.order"

    @api.model
    def _careos_demo_lab(self):
        """Synthetic lab work for today's demo visits (prototype worklist)."""
        def encounter_for(patient_xmlid):
            patient = self.env.ref(f"careos_patients.{patient_xmlid}")
            return self.env["careos.encounter"].search([("patient_id", "=", patient.id)], limit=1)

        def test(xmlid):
            return self.env.ref(f"careos_laboratory.{xmlid}")

        ahmed = encounter_for("patient_ahmed_hassan")
        if ahmed:
            order = self.create({"encounter_id": ahmed.id, "test_ids": [(6, 0, test("test_lipid").ids)], "clinical_note": "Fasting sample"})
            order.action_collect()
            order.action_process()
        sara = encounter_for("patient_sara_ibrahim")
        if sara:
            order = self.create({"encounter_id": sara.id, "test_ids": [(6, 0, (test("test_cbc") | test("test_hba1c")).ids)]})
            order.action_collect()
            order.action_process()
            values = {"Hemoglobin": 12.9, "WBC": 7.2, "Platelets": 245, "HbA1c": 7.4}
            order.action_submit_results({str(r.id): values[r.parameter_id.name] for r in order.result_ids})
        mona = encounter_for("patient_mona_youssef")
        if mona:
            order = self.create({"encounter_id": mona.id, "test_ids": [(6, 0, test("test_glucose").ids)]})
            order.action_collect()
            order.action_process()
            order.action_submit_results({str(order.result_ids.id): 94})
            order.action_verify()
