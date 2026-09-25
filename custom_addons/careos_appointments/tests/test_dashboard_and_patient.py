from datetime import timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import FROZEN_NOW, NOW, CareosAppointmentCase


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestReceptionDashboard(CareosAppointmentCase):
    def kpis(self, user):
        dashboard = self.env["careos.appointment"].with_user(user).careos_reception_dashboard()
        return {k["key"]: k["value"] for k in dashboard["kpis"]}, dashboard

    def test_counts_come_from_todays_records(self):
        Patient = self.env["careos.patient"]
        patients = Patient.create([{"name": f"Dash Patient {i}"} for i in range(6)])

        def appt(i, minutes):
            return self.book(patient_id=patients[i].id, start=NOW + timedelta(minutes=minutes),
                             provider_id=self.env["careos.provider"].create(
                                 {"name": f"Dr. Dash {i}", "branch_ids": [(6, 0, self.branch_a.ids)]}).id)

        done = appt(0, -120)
        self.bring_to_done(done)
        in_progress = appt(1, -60)
        in_progress.action_check_in()
        in_progress.action_start()
        checked_in = appt(2, -30)
        checked_in.action_check_in()
        no_show = appt(3, -90)
        no_show.action_no_show()
        appt(4, 60).action_cancel("Patient request")
        appt(5, 90)  # confirmed, upcoming
        # Noise that must not be counted: another branch, another day.
        self.book(branch_id=self.branch_b.id, provider_id=self.provider_b.id, start=NOW + timedelta(hours=1))
        self.book(start=NOW + timedelta(days=1), patient_id=self.patient2.id)

        kpis, dashboard = self.kpis(self.reception)
        self.assertEqual(kpis["booked"], 5)  # cancelled excluded
        self.assertEqual(kpis["arrived"], 3)  # done + in progress + checked in
        self.assertEqual(kpis["in_progress"], 1)
        self.assertEqual(kpis["done"], 1)
        self.assertEqual(kpis["no_show"], 1)
        self.assertEqual(len(dashboard["appointments"]), 5)
        self.assertEqual([a["patient"]["name"] for a in dashboard["upcoming"]], ["Dash Patient 5"])
        self.assertEqual(dashboard["date"], "2030-03-12")

    def bring_to_done(self, appointment):
        appointment.action_check_in()
        appointment.action_start()
        appointment.action_complete()

    def test_dashboard_follows_current_branch(self):
        self.book(start=NOW + timedelta(hours=1))
        kpis, dashboard = self.kpis(self.reception_b)
        self.assertEqual(kpis["booked"], 0)
        self.assertEqual(dashboard["branch"]["id"], self.branch_b.id)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_dashboard_role_access(self):
        self.kpis(self.manager)
        self.kpis(self.nurse)
        with self.assertRaises(AccessError):
            self.kpis(self.lab)

    def test_dashboard_requires_branch(self):
        self.reception.write({"careos_branch_id": False})
        with self.assertRaises(UserError):
            self.kpis(self.reception)


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestPatient360Appointments(CareosAppointmentCase):
    def test_profile_shows_next_appointment_and_count(self):
        past = self.book(start=NOW - timedelta(hours=2))
        past.action_no_show()
        upcoming = self.book(start=NOW + timedelta(hours=2))
        profile = self.patient.with_user(self.reception).careos_get_profile()
        self.assertTrue(profile["appointments_access"])
        self.assertEqual(profile["next_appointment"]["id"], upcoming.id)
        self.assertEqual(profile["appointment_count"], 2)
        self.assertTrue(profile["can_book"])
        data = self.patient.with_user(self.reception).careos_get_appointments()
        self.assertEqual([a["id"] for a in data["upcoming"]], upcoming.ids)
        self.assertEqual([a["id"] for a in data["past"]], past.ids)

    def test_checked_in_visit_is_current(self):
        earlier = self.book(start=NOW - timedelta(hours=1))
        self.book(start=NOW + timedelta(hours=2), provider_id=self.provider2.id)
        earlier.action_check_in()
        profile = self.patient.careos_get_profile()
        self.assertEqual(profile["next_appointment"]["id"], earlier.id)

    def test_timeline_includes_appointment_lifecycle(self):
        appointment = self.book(start=NOW - timedelta(minutes=5))
        appointment.action_check_in()
        appointment.action_start()
        appointment.action_complete()
        timeline = self.patient.with_user(self.reception).careos_get_profile()["timeline"]
        titles = [e["title"] for e in timeline]
        for title in ("Appointment booked", "Appointment confirmed", "Patient checked in",
                      "Consultation started", "Visit completed", "Patient registered"):
            self.assertIn(title, titles)
        # Same-second events keep lifecycle order (newest first).
        lifecycle = [t for t in titles if t != "Patient registered"]
        self.assertLess(lifecycle.index("Visit completed"), lifecycle.index("Consultation started"))
        self.assertLess(lifecycle.index("Consultation started"), lifecycle.index("Patient checked in"))

    def test_cancellation_reason_on_timeline(self):
        self.book(start=NOW + timedelta(hours=1)).action_cancel("Provider unavailable")
        cancelled = [e for e in self.patient.careos_get_profile()["timeline"] if e["title"] == "Appointment cancelled"]
        self.assertIn("Provider unavailable", cancelled[0]["detail"])

    def test_roles_without_appointment_access(self):
        self.book(start=NOW + timedelta(hours=1))
        profile = self.patient.with_user(self.lab).careos_get_profile()
        self.assertFalse(profile["appointments_access"])
        self.assertNotIn("next_appointment", profile)
        self.assertFalse([e for e in profile["timeline"] if e.get("kind") == "appointment"])

    def test_doctor_timeline_limited_to_own_appointments(self):
        self.book(start=NOW + timedelta(hours=1), provider_id=self.provider2.id)
        profile = self.patient.with_user(self.doctor).careos_get_profile()
        self.assertEqual(profile["appointment_count"], 0)
        self.assertFalse([e for e in profile["timeline"] if e.get("kind") == "appointment"])
