from datetime import datetime, timedelta

import pytz

from odoo import api, models


class CareosAppointment(models.Model):
    _inherit = "careos.appointment"

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    @api.model
    def _careos_demo_schedule(self):
        """Synthetic schedule for demo databases: today's clinic at the Cairo
        branch plus the coming days. Uses the real booking workflow."""
        env = self.env
        branch = env.ref("careos_base.branch_cairo")
        types = {
            "new": env.ref("careos_appointments.type_new_patient"),
            "follow": env.ref("careos_appointments.type_follow_up"),
            "consult": env.ref("careos_appointments.type_consultation"),
        }
        saeed = env.ref("careos_appointments.provider_saeed")
        fathy = env.ref("careos_appointments.provider_fathy")
        elsayed = env.ref("careos_appointments.provider_elsayed")
        patient = lambda xmlid: env.ref(f"careos_patients.{xmlid}")
        tz = branch._careos_tz()
        today = branch._careos_today()

        def at(day_offset, hour, minute=0):
            local = tz.localize(datetime.combine(today + timedelta(days=day_offset), datetime.min.time()).replace(hour=hour, minute=minute))
            return local.astimezone(pytz.utc).replace(tzinfo=None)

        plan = [
            (0, 9, 0, "patient_mona_youssef", saeed, "follow", "Blood pressure review"),
            (0, 9, 30, "patient_karim_adel", saeed, "new", "Chest discomfort on exertion"),
            (0, 10, 0, "patient_sara_ibrahim", fathy, "consult", "Diabetes follow-up"),
            (0, 10, 30, "patient_ahmed_hassan", saeed, "follow", "Hypertension follow-up"),
            (0, 11, 0, "patient_omar_nabil", fathy, "consult", "Recurring headaches"),
            (0, 11, 30, "patient_laila_hassan", saeed, "follow", "Post-medication review"),
            (0, 12, 0, "patient_karim_adel", elsayed, "consult", "Lab results discussion"),
            (1, 9, 0, "patient_omar_nabil", saeed, "follow", "Follow-up"),
            (2, 10, 30, "patient_ahmed_hassan", fathy, "consult", "Annual check"),
        ]
        rooms = {saeed: env.ref("careos_appointments.room_cairo_3"), fathy: env.ref("careos_appointments.room_cairo_5"),
                 elsayed: env.ref("careos_appointments.room_cairo_2")}
        for day_offset, hour, minute, patient_xmlid, provider, type_key, reason in plan:
            self.create({
                "patient_id": patient(patient_xmlid).id,
                "provider_id": provider.id,
                "type_id": types[type_key].id,
                "branch_id": branch.id,
                "room_id": rooms[provider].id,
                "start": at(day_offset, hour, minute),
                "reason": reason,
            }).action_confirm()

    @api.model
    def _careos_demo_queue(self):
        """Move part of today's demo schedule through check-in and the queue,
        using the real workflow."""
        env = self.env
        ref = env.ref
        steps = [
            ("patient_mona_youssef", ("check_in", "call", "start", "complete")),
            ("patient_karim_adel", ("check_in", "call", "start")),
            ("patient_sara_ibrahim", ("check_in", "call")),
            ("patient_ahmed_hassan", ("check_in",)),
        ]
        branch = ref("careos_base.branch_cairo")
        day_start, day_end = branch._careos_day_bounds()
        for patient_xmlid, actions in steps:
            appointment = self.search([
                ("patient_id", "=", ref(f"careos_patients.{patient_xmlid}").id),
                ("start", ">=", day_start), ("start", "<", day_end), ("state", "=", "confirmed"),
            ], order="start", limit=1)
            for action in actions:
                if action == "call":
                    appointment.queue_ticket_ids.action_call()
                else:
                    getattr(appointment, f"action_{action}")()
