from odoo import fields, models


class CareosPatient(models.Model):
    _inherit = "careos.patient"

    appointment_ids = fields.One2many("careos.appointment", "patient_id", string="Appointments")

    def _careos_appointment_access(self):
        return self.env["careos.appointment"].has_access("read")

    def careos_get_profile(self):
        profile = super().careos_get_profile()
        access = self._careos_appointment_access()
        profile["appointments_access"] = access
        if access:
            Appointment = self.env["careos.appointment"]
            upcoming = Appointment.search(
                [("patient_id", "=", self.id), ("state", "in", ("draft", "confirmed", "checked_in", "in_progress")),
                 ("stop", ">=", fields.Datetime.now())],
                order="start", limit=1,
            )
            # A patient who is already checked in or being seen is "current"
            # even if the booked slot has technically passed.
            current = Appointment.search(
                [("patient_id", "=", self.id), ("state", "in", ("checked_in", "in_progress"))], order="start", limit=1,
            )
            next_appointment = current or upcoming
            profile["next_appointment"] = next_appointment._careos_payload() if next_appointment else False
            profile["appointment_count"] = Appointment.search_count([("patient_id", "=", self.id)])
            profile["can_book"] = Appointment._careos_role_allows("edit") and Appointment.has_access("create")
        return profile

    def _careos_timeline_events(self, limit=30):
        events = super()._careos_timeline_events(limit)
        if self._careos_appointment_access():
            appointments = self.env["careos.appointment"].search(
                [("patient_id", "=", self.id)], order="start desc", limit=limit,
            )
            for appointment in appointments:
                summary = appointment._careos_summary()
                for event in appointment._careos_history():
                    detail = " · ".join(filter(None, [summary, event["detail"]]))
                    events.append({**event, "kind": "appointment", "detail": detail, "appointment_id": appointment.id})
            events.sort(key=lambda e: (e["date"], e.get("rank", 0)), reverse=True)
        return events[:limit]

    def careos_get_appointments(self):
        """Upcoming and past appointments for the Patient 360 tab."""
        self.ensure_one()
        self.check_access("read")
        Appointment = self.env["careos.appointment"]
        Appointment.check_access("read")
        now = fields.Datetime.now()
        appointments = Appointment.search([("patient_id", "=", self.id)], order="start desc")
        upcoming = appointments.filtered(
            lambda a: a.state in ("draft", "confirmed", "checked_in", "in_progress") and (a.stop >= now or a.state in ("checked_in", "in_progress"))
        ).sorted("start")
        return {
            "upcoming": [a._careos_payload() for a in upcoming],
            "past": [a._careos_payload() for a in appointments - upcoming],
        }
