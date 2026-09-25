from odoo import _, api, fields, models


class CareosEncounter(models.Model):
    _inherit = "careos.encounter"

    lab_order_ids = fields.One2many("careos.lab.order", "encounter_id", string="Lab orders")

    def _careos_extend_workspace(self, payload):
        payload = super()._careos_extend_workspace(payload)
        Order = self.env["careos.lab.order"]
        payload["lab_orders"] = [o._careos_payload(with_results=True) for o in Order.search([("encounter_id", "=", self.id)])] \
            if Order.has_access("read") else []
        payload["can_order_lab"] = self.state == "open" and ("doctor" in self.env.user._careos_role_keys() or self.env.su)
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


class CareosLabOrder(models.Model):
    _inherit = "careos.lab.order"

    @api.model
    def _careos_demo_lab(self):
        """Synthetic lab work for today's demo visits (prototype worklist)."""
        def encounter_for(patient_xmlid):
            patient = self.env.ref(f"careos_patients.{patient_xmlid}")
            return self.env["careos.encounter"].search([("patient_id", "=", patient.id)], limit=1)

        def test(xmlid):
            return self.env.ref(f"careos_laboratory.{xmlid}")

        ahmed = encounter_for("patient_ahmed_hassan")
        if ahmed:
            order = self.create({"encounter_id": ahmed.id, "test_ids": [(6, 0, test("test_lipid").ids)], "clinical_note": "Fasting sample"})
            order.action_collect()
            order.action_process()
        sara = encounter_for("patient_sara_ibrahim")
        if sara:
            order = self.create({"encounter_id": sara.id, "test_ids": [(6, 0, (test("test_cbc") | test("test_hba1c")).ids)]})
            order.action_collect()
            order.action_process()
            values = {"Hemoglobin": 12.9, "WBC": 7.2, "Platelets": 245, "HbA1c": 7.4}
            order.action_submit_results({str(r.id): values[r.parameter_id.name] for r in order.result_ids})
        mona = encounter_for("patient_mona_youssef")
        if mona:
            order = self.create({"encounter_id": mona.id, "test_ids": [(6, 0, test("test_glucose").ids)]})
            order.action_collect()
            order.action_process()
            order.action_submit_results({str(order.result_ids.id): 94})
            order.action_verify()
