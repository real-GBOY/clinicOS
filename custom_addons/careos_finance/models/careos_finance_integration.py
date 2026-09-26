from odoo import api, models
from odoo.addons.careos_base.models.authorization import has_role

from .careos_billing import VIEW_ROLES

# Visit prices for the default visit types (EGP, as in the CareOS prototype).
DEFAULT_TYPE_PRICES = {"New patient": 600.0, "Follow-up": 450.0, "Consultation": 500.0}


class CareosSearch(models.AbstractModel):
    _inherit = "careos.search"

    @api.model
    def careos_global_search(self, query, limit=5):
        """Invoices are searched through the billing service (front-desk roles
        have no accounting rights), limited to the user's branches."""
        results = super().careos_global_search(query, limit)
        query = (query or "").strip()
        if len(query) >= 2 and has_role(self.env, VIEW_ROLES):
            for row in self.env["careos.billing"].careos_invoice_list(query=query, limit=limit):
                results.append({
                    "model": "account.move", "kind": "Invoice", "screen": "invoice", "id": row["id"],
                    "title": row["name"],
                    "detail": f"{row['patient']['name']} · {row['balance']:,.0f} {row['currency']} due · {row['status_label']}",
                })
        return results


class CareosAppointmentType(models.Model):
    _inherit = "careos.appointment.type"

    @api.model
    def _careos_install_prices(self):
        self._careos_init_products(DEFAULT_TYPE_PRICES)
