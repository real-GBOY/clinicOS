from odoo import models


class CareosQueueTicket(models.Model):
    _inherit = "careos.queue.ticket"

    def _careos_payload(self, position=None):
        payload = super()._careos_payload(position)
        encounter = self.sudo().appointment_id.encounter_ids[:1].with_env(self.env)
        readable = encounter and encounter.has_access("read")
        payload["encounter"] = {
            "id": encounter.id,
            "has_vitals": bool(encounter.vitals_recorded_at),
            "can_record_vitals": encounter.state == "open" and encounter.has_access("write"),
        } if readable else False
        return payload
