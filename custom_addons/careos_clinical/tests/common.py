from datetime import timedelta

from odoo.tests import new_test_user

from odoo.addons.careos_appointments.tests.common import NOW, CareosAppointmentCase


class CareosVisitCase(CareosAppointmentCase):
    """Adds pharmacist/finance users and a helper that brings a patient to
    an open encounter through the real workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        branch_vals = {"careos_branch_ids": [(6, 0, cls.branch_a.ids)], "careos_branch_id": cls.branch_a.id}
        cls.pharmacist = new_test_user(cls.env, login="v_pharmacist", groups="careos_base.group_careos_pharmacist", **branch_vals)
        cls.env["careos.patient.allergy"].create({"patient_id": cls.patient.id, "allergen": "Penicillin", "severity": "severe"})

    def visit(self, started=True, **vals):
        """Booked, checked in (encounter opened), optionally started."""
        vals.setdefault("start", NOW - timedelta(minutes=5))
        appointment = self.book(**vals)
        appointment.with_user(self.reception).action_check_in()
        if started:
            # The front desk may start any visit; doctors only their own.
            appointment.with_user(self.reception).action_start()
        return appointment, appointment.encounter_ids

    def diagnose(self, encounter, code="I10", description="Essential hypertension"):
        return self.env["careos.diagnosis"].with_user(self.doctor).create({
            "encounter_id": encounter.id, "code": code, "description": description, "is_primary": True,
        })
