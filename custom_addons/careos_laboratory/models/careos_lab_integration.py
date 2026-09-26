from odoo import _, api, fields, models
from odoo.addons.careos_base.models.authorization import has_role


class CareosEncounter(models.Model):
    _inherit = "careos.encounter"

    lab_order_ids = fields.One2many("careos.lab.order", "encounter_id", string="Lab orders")

    def _careos_extend_workspace(self, payload):
        payload = super()._careos_extend_workspace(payload)
        Order = self.env["careos.lab.order"]
        payload["lab_orders"] = [o._careos_payload(with_results=True) for o in Order.search([("encounter_id", "=", self.id)])] \
            if Order.has_access("read") else []
        payload["can_order_lab"] = self.state == "open" and has_role(self.env, "doctor")
        return payload

    def careos_order_lab(self, test_ids, priority="routine", note=""):
        self.ensure_one()
        order = self.env["careos.lab.order"].create({
            "encounter_id": self.id, "test_ids": [(6, 0, test_ids)], "priority": priority, "clinical_note": note,
        })
        return order.id


class CareosAppointment(models.Model):
    _inherit = "careos.appointment"

    @api.model
    def careos_doctor_dashboard(self):
        dashboard = super().careos_doctor_dashboard()
        Order = self.env["careos.lab.order"]
        providers = self.env["careos.provider"].search([("user_id", "=", self.env.uid)])
        orders = Order.search([("provider_id", "in", providers.ids), ("state", "!=", "completed")], limit=10)
        dashboard["panels"]["lab"] = [o._careos_payload() for o in orders]
        return dashboard


class CareosPatient(models.Model):
    _inherit = "careos.patient"

    def careos_get_profile(self):
        profile = super().careos_get_profile()
        profile["lab_access"] = self.env["careos.lab.order"].has_access("read")
        return profile

    def careos_get_lab_results(self):
        self.ensure_one()
        self.check_access("read")
        orders = self.env["careos.lab.order"].search([("patient_id", "=", self.id)])
        return [o._careos_payload(with_results=o.state in ("result_entered", "verified", "completed")) for o in orders]

    def _careos_timeline_events(self, limit=30):
        events = super()._careos_timeline_events(limit)
        Order = self.env["careos.lab.order"]
        if Order.has_access("read"):
            for order in Order.search([("patient_id", "=", self.id)], limit=limit):
                tests = ", ".join(order.test_ids.mapped("name"))
                events.append({"key": f"lab-{order.id}-ordered", "date": fields.Datetime.to_string(order.create_date),
                               "rank": 7, "kind": "lab", "title": _("Lab order placed"), "detail": tests, "tone": "warning"})
                if order.verified_at:
                    detail = tests + (_(" · abnormal values") if order.has_abnormal else "")
                    events.append({"key": f"lab-{order.id}-verified", "date": fields.Datetime.to_string(order.verified_at),
                                   "rank": 8, "kind": "lab", "title": _("Lab results verified"), "detail": detail,
                                   "tone": "danger" if order.has_abnormal else "success"})
            events.sort(key=lambda e: (e["date"], e.get("rank", 0)), reverse=True)
        return events[:limit]


class CareosSearch(models.AbstractModel):
    _inherit = "careos.search"

    @api.model
    def _careos_search_providers(self):
        return super()._careos_search_providers() + [
            {"model": "careos.lab.order", "kind": "Lab Order", "screen": "lab", "sequence": 8},
        ]
