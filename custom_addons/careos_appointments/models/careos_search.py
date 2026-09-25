from odoo import api, models


class CareosSearch(models.AbstractModel):
    _inherit = "careos.search"

    @api.model
    def _careos_search_providers(self):
        return super()._careos_search_providers() + [
            {"model": "careos.appointment", "kind": "Appointment", "screen": "appointment", "sequence": 5},
        ]
