from odoo import api, models


class CareosSearch(models.AbstractModel):
    _inherit = "careos.search"

    @api.model
    def _careos_search_providers(self):
        return super()._careos_search_providers() + [
            {"model": "careos.patient", "kind": "Patient", "screen": "patient", "sequence": 1},
        ]
