from odoo import _, api, fields, models


class CareosAppointment(models.Model):
    _inherit = "careos.appointment"

    encounter_ids = fields.One2many("careos.encounter", "appointment_id", string="Encounter")

    def _careos_after_transition(self, action):
        super()._careos_after_transition(action)
        now = fields.Datetime.now()
        if action == "check_in":
            # Opened on the patient's behalf as part of check-in (the front desk
            # cannot read or write clinical records themselves).
            self.env["careos.encounter"].sudo().create([{"appointment_id": a.id} for a in self])
        elif action == "start":
            self.sudo().encounter_ids.with_context(careos_encounter_internal=True).write({"started_at": now})

    def _careos_payload(self):
        payload = super()._careos_payload()
        # Look the link up with sudo (non-clinical roles cannot read encounters)
        # and only expose it to users who may open the clinical record.
        encounter = self.sudo().encounter_ids[:1].with_env(self.env)
        payload["encounter_id"] = encounter.id if encounter and encounter.has_access("read") else False
        return payload

    @api.model
    def careos_doctor_dashboard(self):
        """Doctor Workspace: own schedule today, unsigned encounters,
        follow-ups due. Extended by the lab module (pending results)."""
        user = self.env.user
        branch = user.careos_branch_id
        providers = self.env["careos.provider"].search([("user_id", "=", user.id)])
        day_start, day_end = branch._careos_day_bounds() if branch else (False, False)
        domain = [("provider_id", "in", providers.ids), ("state", "!=", "cancelled")]
        if branch:
            domain += [("start", ">=", day_start), ("start", "<", day_end)]
        today = self.search(domain)
        Encounter = self.env["careos.encounter"]
        unsigned = Encounter.search([("provider_id", "in", providers.ids), ("state", "=", "open"),
                                     ("appointment_id.state", "in", ("done", "no_show"))])
        return {
            "provider": providers[:1].name or user.name,
            "department": user.careos_department_id.name or (providers[:1].specialty or ""),
            "schedule": [a._careos_payload() for a in today],
            "unsigned": [e._careos_summary_payload() for e in unsigned],
            "follow_ups": Encounter.careos_follow_ups(),
            "panels": {},
        }
