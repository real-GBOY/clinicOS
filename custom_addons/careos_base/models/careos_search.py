from odoo import api, models


class CareosSearch(models.AbstractModel):
    """Global search backing the CareOS command palette.

    Each domain module registers what it can be searched for by extending
    ``_careos_search_providers``. Searches always run with the caller's
    rights, so a record is only returned if the user could open it anyway.
    """

    _name = "careos.search"
    _description = "CareOS Global Search"

    @api.model
    def _careos_search_providers(self):
        """Return a list of dicts: model, kind (label shown), screen (client
        screen to open), sequence."""
        return []

    @api.model
    def careos_global_search(self, query, limit=5):
        query = (query or "").strip()
        if len(query) < 2:
            return []
        results = []
        for provider in sorted(self._careos_search_providers(), key=lambda p: p.get("sequence", 10)):
            Model = self.env[provider["model"]]
            if not Model.has_access("read"):
                continue
            for record in Model._careos_search(query, limit):
                results.append({
                    "model": provider["model"],
                    "kind": provider["kind"],
                    "screen": provider["screen"],
                    **record._careos_search_result(),
                })
        return results


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def _careos_search(self, query, limit):
        return self.search([("display_name", "ilike", query)], limit=limit)

    def _careos_search_result(self):
        self.ensure_one()
        return {"id": self.id, "title": self.display_name, "detail": ""}
