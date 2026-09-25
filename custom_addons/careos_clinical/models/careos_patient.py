from odoo import _, fields, models


class CareosPatient(models.Model):
    _inherit = "careos.patient"

    encounter_ids = fields.One2many("careos.encounter", "patient_id", string="Encounters")

    def careos_get_profile(self):
        profile = super().careos_get_profile()
        profile["encounters_access"] = self.env["careos.encounter"].has_access("read")
        return profile

    def _careos_timeline_events(self, limit=30):
        events = super()._careos_timeline_events(limit)
        Encounter = self.env["careos.encounter"]
        if Encounter.has_access("read"):
            for encounter in Encounter.search([("patient_id", "=", self.id), ("state", "=", "done")], limit=limit):
                summary = encounter._careos_summary_payload()
                events.append({
                    "key": f"enc-{encounter.id}",
                    "date": fields.Datetime.to_string(encounter.completed_at),
                    "rank": 6,
                    "kind": "encounter",
                    "title": _("Encounter completed"),
                    "detail": " · ".join(filter(None, [summary["diagnosis"], encounter.provider_id.name])),
                    "tone": "info",
                })
            events.sort(key=lambda e: (e["date"], e.get("rank", 0)), reverse=True)
        return events[:limit]

    def careos_get_encounters(self):
        self.ensure_one()
        self.check_access("read")
        return [e._careos_summary_payload() for e in self.env["careos.encounter"].search([("patient_id", "=", self.id)])]
