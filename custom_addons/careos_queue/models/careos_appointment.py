from odoo import _, api, fields, models


class CareosAppointment(models.Model):
    _inherit = "careos.appointment"

    queue_ticket_ids = fields.One2many("careos.queue.ticket", "appointment_id", string="Queue ticket")

    def _careos_after_transition(self, action):
        """Check-in issues a queue ticket; later transitions move it. Runs in
        the same transaction as the appointment change, so either both are
        saved or neither is."""
        super()._careos_after_transition(action)
        Ticket = self.env["careos.queue.ticket"]
        if action == "check_in":
            for appointment in self:
                Ticket._careos_create_for(appointment)
        else:
            self.queue_ticket_ids._careos_sync(action)

    def _careos_payload(self):
        payload = super()._careos_payload()
        ticket = self.queue_ticket_ids[:1]
        payload["queue_ticket"] = {
            "id": ticket.id,
            "label": f"#{ticket.number:03d}",
            "state": ticket.state,
            "state_label": dict(ticket._fields["state"].selection)[ticket.state],
            "room": ticket.room_id.name or "",
        } if ticket else False
        return payload

    def _careos_history(self):
        events = super()._careos_history()
        ticket = self.queue_ticket_ids[:1]
        if ticket.called_at:
            detail = ticket.room_id.name or ""
            events.append({
                "key": f"appt-{self.id}-called",
                "date": fields.Datetime.to_string(ticket.called_at),
                "rank": 3,
                "title": _("Patient called"),
                "detail": detail,
                "tone": "info",
            })
            events.sort(key=lambda e: (e["date"], e["rank"]))
        return events

    @api.model
    def careos_reception_dashboard(self):
        dashboard = super().careos_reception_dashboard()
        board = self.env["careos.queue.ticket"].careos_queue_board()
        waiting = board["waiting"]
        dashboard["kpis"].append({
            "key": "waiting", "label": _("Waiting"), "value": len(waiting), "sequence": 30,
            "tone": "warning" if waiting else "",
        })
        dashboard["kpis"].sort(key=lambda k: k["sequence"])
        dashboard["queue"] = {"waiting": waiting[:6], "in_consultation": board["in_consultation"]}
        return dashboard

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
