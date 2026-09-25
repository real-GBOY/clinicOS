from odoo import api, models

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
        roles = set(self.env.user._careos_role_keys())
        if len(query) >= 2 and roles & {"reception", "finance", "manager", "admin"}:
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


class CareosBilling(models.AbstractModel):
    _inherit = "careos.billing"

    @api.model
    def _careos_demo_billing(self):
        """Bill today's completed demo visit and take a part payment."""
        mona = self.env.ref("careos_patients.patient_mona_youssef")
        appointment = self.env["careos.appointment"].search([("patient_id", "=", mona.id), ("state", "=", "done")], limit=1)
        if appointment:
            move_id = self.careos_create_invoice(appointment.id)
            self.careos_post(move_id)
            self.careos_register_payment(move_id, 400.0, "card")
