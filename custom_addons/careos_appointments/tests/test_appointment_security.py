from datetime import timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import FROZEN_NOW, NOW, CareosAppointmentCase

ACL_LOGGERS = ("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.models")


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestAppointmentSecurity(CareosAppointmentCase):
    """Spec §9 matrix for Appointments, enforced on the server:
    Reception full · Doctor own schedule · Nurse read · Lab/Pharmacy/Finance
    none · Manager read · Admin full (no check-in)."""

    def test_reception_books_and_runs_the_day(self):
        appointment = self.book(user=self.reception, start=NOW + timedelta(minutes=5))
        appointment.action_check_in()
        appointment.action_start()
        appointment.action_complete()
        self.assertEqual(appointment.state, "done")

    @mute_logger(*ACL_LOGGERS)
    def test_doctor_sees_and_runs_only_own_schedule(self):
        own = self.book(start=NOW + timedelta(minutes=5))
        other = self.book(start=NOW + timedelta(minutes=5), provider_id=self.provider2.id, patient_id=self.patient2.id)
        Appointment = self.env["careos.appointment"].with_user(self.doctor)
        self.assertEqual(Appointment.search([]), own)
        with self.assertRaises(AccessError):
            other.with_user(self.doctor).read(["name"])
        # Doctors cannot check patients in (front-desk action)…
        with self.assertRaises(AccessError):
            own.with_user(self.doctor).action_check_in()
        own.action_check_in()
        # …but run their own consultation.
        own.with_user(self.doctor).action_start()
        own.with_user(self.doctor).action_complete()
        self.assertEqual(own.state, "done")
        # And cannot book.
        with self.assertRaises(AccessError):
            self.book(user=self.doctor, patient_id=self.patient2.id, start=NOW + timedelta(hours=2))

    @mute_logger(*ACL_LOGGERS)
    def test_doctor_cannot_start_another_doctors_patient(self):
        other = self.book(provider_id=self.provider2.id)
        other.action_check_in()
        with self.assertRaises(AccessError):
            other.with_user(self.doctor).action_start()

    @mute_logger(*ACL_LOGGERS)
    def test_nurse_reads_but_cannot_change(self):
        appointment = self.book()
        self.assertEqual(appointment.with_user(self.nurse).patient_id, self.patient)
        for action in ("action_check_in", "action_no_show"):
            with self.subTest(action=action), self.assertRaises(AccessError):
                getattr(appointment.with_user(self.nurse), action)()

    @mute_logger(*ACL_LOGGERS)
    def test_roles_without_appointment_access(self):
        self.book()
        for user in (self.lab, self.finance):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.env["careos.appointment"].with_user(user).search([])

    @mute_logger(*ACL_LOGGERS)
    def test_manager_reads_only(self):
        appointment = self.book()
        self.assertEqual(self.env["careos.appointment"].with_user(self.manager).search([]), appointment)
        with self.assertRaises(AccessError):
            appointment.with_user(self.manager).action_cancel("Not allowed")

    @mute_logger(*ACL_LOGGERS)
    def test_admin_books_and_cancels_but_does_not_check_in(self):
        appointment = self.book(user=self.careos_admin, start=NOW + timedelta(hours=1))
        with self.assertRaises(AccessError):
            appointment.action_check_in()
        appointment.action_cancel("Rebooked")
        self.assertEqual(appointment.state, "cancelled")

    @mute_logger(*ACL_LOGGERS)
    def test_branch_isolation(self):
        at_a = self.book(user=self.reception, start=NOW + timedelta(hours=1))
        at_b = self.book(user=self.reception_b, branch_id=self.branch_b.id, patient_id=self.patient2.id,
                         start=NOW + timedelta(hours=3))
        self.assertEqual(self.env["careos.appointment"].with_user(self.reception).search([]), at_a)
        self.assertEqual(self.env["careos.appointment"].with_user(self.reception_b).search([]), at_b)
        with self.assertRaises(AccessError):
            at_b.with_user(self.reception).read(["name"])
        with self.assertRaises(AccessError):
            at_b.with_user(self.reception).action_check_in()
        # Branch A staff cannot create bookings at branch B either.
        with self.assertRaises(AccessError):
            self.book(user=self.reception, branch_id=self.branch_b.id, start=NOW + timedelta(hours=5),
                      patient_id=self.patient2.id)

    def test_global_search_respects_branch_and_role(self):
        at_a = self.book(start=NOW + timedelta(hours=1))
        self.book(branch_id=self.branch_b.id, provider_id=self.provider_b.id, patient_id=self.patient2.id,
                  start=NOW + timedelta(hours=1))
        Search = self.env["careos.search"]
        found = [r for r in Search.with_user(self.reception).careos_global_search("Appointment Patient") if r["model"] == "careos.appointment"]
        self.assertEqual([r["id"] for r in found], at_a.ids)
        self.assertEqual(found[0]["screen"], "appointment")
        by_ref = Search.with_user(self.reception).careos_global_search(at_a.name)
        self.assertIn(at_a.id, [r["id"] for r in by_ref if r["model"] == "careos.appointment"])
        lab_results = Search.with_user(self.lab).careos_global_search("Appointment Patient")
        self.assertFalse([r for r in lab_results if r["model"] == "careos.appointment"])
