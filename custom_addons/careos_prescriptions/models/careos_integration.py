from odoo import _, api, fields, models
from odoo.addons.careos_base.models.authorization import has_role


class CareosEncounter(models.Model):
    _inherit = "careos.encounter"

    prescription_ids = fields.One2many("careos.prescription", "encounter_id", string="Prescriptions")

    def _careos_extend_workspace(self, payload):
        payload = super()._careos_extend_workspace(payload)
        Rx = self.env["careos.prescription"]
        payload["prescriptions"] = [rx._careos_payload() for rx in Rx.search([("encounter_id", "=", self.id)])] \
            if Rx.has_access("read") else []
        payload["can_prescribe"] = self.state == "open" and has_role(self.env, "doctor")
        return payload

    def careos_new_prescription(self):
        """Open a draft prescription for this encounter (or return the existing draft)."""
        self.ensure_one()
        draft = self.env["careos.prescription"].search([("encounter_id", "=", self.id), ("state", "=", "draft")], limit=1)
        if not draft:
            draft = self.env["careos.prescription"].create({"encounter_id": self.id})
        return draft.id


class CareosPatient(models.Model):
    _inherit = "careos.patient"

    def _careos_current_medication_lines(self):
        Line = self.env["careos.prescription.line"]
        if not Line.has_access("read"):
            return Line
        return Line.search([("patient_id", "=", self.id), ("state", "in", ("issued", "dispensed"))])

    def careos_get_profile(self):
        profile = super().careos_get_profile()
        Line = self.env["careos.prescription.line"]
        profile["medications_access"] = Line.has_access("read")
        if profile["medications_access"]:
            profile["current_medications"] = [line._careos_payload() for line in self._careos_current_medication_lines()]
        return profile

    def _careos_timeline_events(self, limit=30):
        events = super()._careos_timeline_events(limit)
        Rx = self.env["careos.prescription"]
        if Rx.has_access("read"):
            for rx in Rx.search([("patient_id", "=", self.id), ("state", "!=", "draft")], limit=limit):
                # "Lisinopril 10mg (30 tabs)" → "Lisinopril 10mg"
                meds = ", ".join(name.split(" (")[0] for name in rx.line_ids.mapped("product_id.name"))
                if rx.issued_at:
                    events.append({"key": f"rx-{rx.id}-issued", "date": fields.Datetime.to_string(rx.issued_at), "rank": 7,
                                   "kind": "prescription", "title": _("Prescription issued"), "detail": meds, "tone": "info"})
                if rx.dispensed_at:
                    events.append({"key": f"rx-{rx.id}-dispensed", "date": fields.Datetime.to_string(rx.dispensed_at), "rank": 8,
                                   "kind": "prescription", "title": _("Prescription dispensed"), "detail": meds, "tone": "success"})
            events.sort(key=lambda e: (e["date"], e.get("rank", 0)), reverse=True)
        return events[:limit]


class CareosSearch(models.AbstractModel):
    _inherit = "careos.search"

    @api.model
    def _careos_search_providers(self):
        return super()._careos_search_providers() + [
            {"model": "careos.prescription", "kind": "Prescription", "screen": "prescription", "sequence": 7},
        ]
