from odoo import api, models


class CareosSearch(models.AbstractModel):
    _inherit = "careos.search"

    @api.model
    def _careos_search_providers(self):
        return super()._careos_search_providers() + [
            {"model": "careos.encounter", "kind": "Encounter", "screen": "encounter", "sequence": 6},
        ]


class CareosEncounter(models.Model):
    _inherit = "careos.encounter"

    _rec_names_search = ["name", "patient_id.name", "patient_id.ref"]

    def _careos_search_result(self):
        self.ensure_one()
        summary = self._careos_summary_payload()
        return {
            "id": self.id,
            "title": f"{self.name} · {self.patient_id.name}",
            "detail": " · ".join(filter(None, [summary["diagnosis"], self.provider_id.name, summary["state_label"]])),
        }
