from odoo import api, models

# Conversations from the CareOS prototype (synthetic).
DEMO_THREADS = {
    "patient_ahmed_hassan": [
        (True, "Hi, can I reschedule my next appointment to the following week?"),
        (False, "Of course — Dr. Saeed has Tuesday 10:30 or Wednesday 2:00. Which works better?"),
        (True, "Tuesday 10:30 works, thank you!"),
    ],
    "patient_sara_ibrahim": [
        (False, "Your appointment is confirmed. Please bring your glucose diary."),
        (True, "Thank you, see you then."),
    ],
    "patient_karim_adel": [
        (True, "Is the lab result ready?"),
    ],
}


class CareosCommunications(models.AbstractModel):
    _inherit = "careos.communications"

    @api.model
    def _careos_demo_communications(self):
        desk = self.env.ref("careos_base.user_reception")
        for xmlid, thread in DEMO_THREADS.items():
            patient = self.env.ref(f"careos_patients.{xmlid}")
            patient.email = patient.email or f"{patient.name.split()[0].lower()}@example.com"
            for from_patient, text in thread:
                if from_patient:
                    patient._careos_post_from_patient(text)
                else:
                    patient.with_user(desk).careos_send_message(text)
        # Reminders for demo bookings confirmed before this module existed.
        upcoming = self.env["careos.appointment"].search([("state", "=", "confirmed"), ("reminder_ids", "=", False)])
        upcoming._careos_schedule_reminders()
