from datetime import timedelta

from odoo import api, fields, models


class CareosEncounter(models.Model):
    _inherit = "careos.encounter"

    @api.model
    def _careos_demo_clinical(self):
        """Encounters for demo visits that were checked in before this module
        existed, plus synthetic documentation (text from the CareOS prototype)."""
        Appointment = self.env["careos.appointment"]
        pending = Appointment.search([("state", "in", ("checked_in", "in_progress", "done")), ("encounter_ids", "=", False)])
        for appointment in pending:
            self.create({"appointment_id": appointment.id, "started_at": appointment.started_at})

        def encounter_for(patient_xmlid, state):
            patient = self.env.ref(f"careos_patients.{patient_xmlid}")
            return self.search([("patient_id", "=", patient.id), ("appointment_id.state", "=", state)], limit=1)

        today = fields.Date.context_today(self)
        done = encounter_for("patient_mona_youssef", "done")
        if done:
            done.write({
                "bp_systolic": 128, "bp_diastolic": 82, "heart_rate": 72, "temperature": 36.7, "weight": 68, "height": 164,
                "spo2": 99, "chief_complaint": "Routine blood pressure review; no new symptoms.",
                "notes": "BP within target on current therapy. Continue medication and home monitoring.",
                "plan": "Continue amlodipine 5mg. Review in 3 months.",
                "follow_up_date": today + timedelta(days=3), "follow_up_reason": "Blood pressure check",
            })
            self.env["careos.diagnosis"].create({"encounter_id": done.id, "code": "I10", "description": "Essential hypertension", "is_primary": True})
            done.write({"state": "done", "completed_at": fields.Datetime.now(), "completed_by_id": done.provider_id.user_id.id})
        active = encounter_for("patient_karim_adel", "in_progress")
        if active:
            active.write({"bp_systolic": 124, "bp_diastolic": 80, "heart_rate": 88, "temperature": 36.9, "weight": 79,
                          "height": 178, "spo2": 98, "chief_complaint": "Chest discomfort on exertion for two weeks."})
        waiting = encounter_for("patient_ahmed_hassan", "checked_in")
        if waiting:
            waiting.write({
                "bp_systolic": 132, "bp_diastolic": 85, "heart_rate": 76, "temperature": 36.8, "weight": 82, "height": 177,
                "spo2": 98,
                "chief_complaint": "Follow-up for blood pressure management; reports mild dizziness in the mornings, no chest pain.",
                "vitals_recorded_at": fields.Datetime.now(),
            })
