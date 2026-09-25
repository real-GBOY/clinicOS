from datetime import timedelta

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.models.careos_appointment import STATES, TRANSITIONS

from .common import FROZEN_NOW, NOW, CareosAppointmentCase


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestAppointment(CareosAppointmentCase):
    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def test_create_defaults(self):
        appointment = self.book(confirm=False)
        self.assertEqual(appointment.state, "draft")
        self.assertTrue(appointment.name.startswith("APT-"))
        self.assertEqual(appointment.duration, 20)
        self.assertEqual(appointment.stop, appointment.start + timedelta(minutes=20))
        self.assertEqual(appointment.company_id, self.branch_a.company_id)

    def test_required_fields(self):
        for missing in ("patient_id", "provider_id", "type_id", "start"):
            with self.subTest(field=missing), mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
                self.book(confirm=False, **{missing: False})

    def test_cannot_create_in_another_state(self):
        with self.assertRaises(UserError):
            self.book(confirm=False, state="confirmed")

    def test_state_cannot_be_written_directly(self):
        appointment = self.book()
        with self.assertRaises(UserError):
            appointment.write({"state": "done"})

    def test_cannot_book_past_date(self):
        with self.assertRaises(ValidationError):
            self.book(start=NOW - timedelta(days=1))
        # Earlier today is allowed (e.g. a walk-in recorded late).
        self.assertTrue(self.book(start=NOW - timedelta(hours=2)))

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def test_happy_path_sets_timestamps(self):
        appointment = self.book(confirm=False)
        appointment.action_confirm()
        appointment.action_check_in()
        appointment.action_start()
        appointment.action_complete()
        self.assertEqual(appointment.state, "done")
        for field_name in ("confirmed_at", "checked_in_at", "started_at", "completed_at"):
            self.assertEqual(appointment[field_name], NOW, field_name)

    def test_every_transition(self):
        """Every (state, action) pair: allowed pairs succeed and land on the
        target state; all others are rejected by the server."""
        for state, _label in STATES:
            for action, (sources, target) in TRANSITIONS.items():
                with self.subTest(state=state, action=action):
                    # Fresh provider and patient per case so bookings never overlap.
                    provider = self.env["careos.provider"].create(
                        {"name": f"Dr. {state} {action}", "branch_ids": [(6, 0, self.branch_a.ids)]}
                    )
                    patient = self.env["careos.patient"].create({"name": f"Patient {state} {action}"})
                    appointment = self.bring_to(
                        self.book(confirm=False, provider_id=provider.id, patient_id=patient.id), state
                    )
                    call = (lambda a=appointment: a.action_cancel("Reason")) if action == "cancel" else getattr(appointment, f"action_{action}")
                    if state in sources:
                        call()
                        self.assertEqual(appointment.state, target)
                    else:
                        with self.assertRaises(UserError):
                            call()
                        self.assertEqual(appointment.state, state)

    def test_cancel_requires_reason(self):
        appointment = self.book()
        with self.assertRaises(UserError):
            appointment.action_cancel("  ")
        appointment.action_cancel("Patient request")
        self.assertEqual(appointment.cancel_reason, "Patient request")
        self.assertEqual(appointment.cancelled_at, NOW)

    def test_no_show_only_after_start_time(self):
        later = self.book(start=NOW + timedelta(hours=1))
        with self.assertRaises(UserError):
            later.action_no_show()
        earlier = self.book(start=NOW - timedelta(hours=1), patient_id=self.patient2.id)
        earlier.action_no_show()
        self.assertEqual(earlier.state, "no_show")

    def test_check_in_only_on_the_day(self):
        tomorrow = self.book(start=NOW + timedelta(days=1))
        with self.assertRaises(UserError):
            tomorrow.action_check_in()

    def test_available_actions_follow_state(self):
        appointment = self.book(start=NOW + timedelta(hours=1))
        self.assertEqual(appointment.with_user(self.reception)._careos_available_actions(),
                         ["check_in", "cancel", "reschedule"])
        appointment.action_check_in()
        self.assertEqual(appointment.with_user(self.reception)._careos_available_actions(), ["start", "no_show"])
        self.assertEqual(appointment.with_user(self.doctor)._careos_available_actions(), ["start"])

    # ------------------------------------------------------------------
    # Rescheduling
    # ------------------------------------------------------------------

    def test_reschedule_until_check_in(self):
        appointment = self.book(start=NOW + timedelta(hours=1))
        appointment.with_user(self.reception).careos_reschedule({"start": NOW + timedelta(hours=2)})
        self.assertEqual(appointment.start, NOW + timedelta(hours=2))
        appointment.write({"start": NOW + timedelta(minutes=10)})
        appointment.action_check_in()
        with self.assertRaises(UserError):
            appointment.write({"start": NOW + timedelta(hours=3)})

    def test_patient_fixed_once_confirmed(self):
        appointment = self.book()
        with self.assertRaises(UserError):
            appointment.write({"patient_id": self.patient2.id})

    # ------------------------------------------------------------------
    # Scheduling conflicts
    # ------------------------------------------------------------------

    def test_provider_double_booking_rejected(self):
        self.book(start=NOW + timedelta(hours=1))
        with self.assertRaises(ValidationError):
            self.book(start=NOW + timedelta(hours=1, minutes=10), patient_id=self.patient2.id)

    def test_room_double_booking_rejected(self):
        self.book(start=NOW + timedelta(hours=1), room_id=self.room_1.id)
        with self.assertRaises(ValidationError):
            self.book(start=NOW + timedelta(hours=1), room_id=self.room_1.id,
                      provider_id=self.provider2.id, patient_id=self.patient2.id)

    def test_patient_double_booking_rejected(self):
        self.book(start=NOW + timedelta(hours=1))
        with self.assertRaises(ValidationError):
            self.book(start=NOW + timedelta(hours=1, minutes=5), provider_id=self.provider2.id)

    def test_adjacent_and_freed_slots_are_bookable(self):
        first = self.book(start=NOW + timedelta(hours=1))  # 11:00–11:20
        self.book(start=NOW + timedelta(hours=1, minutes=20), patient_id=self.patient2.id)  # back-to-back
        first.action_cancel("Patient request")
        self.book(start=NOW + timedelta(hours=1))  # cancelled slot is free again

    def test_conflict_detected_across_branches(self):
        """A provider booked at branch B by another receptionist is still busy
        for branch A, even though branch A staff cannot see that booking."""
        self.book(start=NOW + timedelta(hours=1), branch_id=self.branch_b.id, user=self.reception_b)
        with self.assertRaises(ValidationError):
            self.book(start=NOW + timedelta(hours=1), patient_id=self.patient2.id, user=self.reception)

    def test_provider_must_practice_at_branch(self):
        with self.assertRaises(ValidationError):
            self.book(provider_id=self.provider2.id, branch_id=self.branch_b.id)

    def test_room_must_be_at_branch(self):
        with self.assertRaises(ValidationError):
            self.book(room_id=self.room_b.id)

    def test_duration_limits(self):
        with self.assertRaises(ValidationError):
            self.book(duration=0)
        with self.assertRaises(ValidationError):
            self.book(duration=9 * 60)

    # ------------------------------------------------------------------
    # Booking API
    # ------------------------------------------------------------------

    def test_book_and_confirm_in_one_call(self):
        payload = self.env["careos.appointment"].with_user(self.reception).careos_book({
            "patient_id": self.patient.id, "provider_id": self.provider.id, "type_id": self.type_consult.id,
            "branch_id": self.branch_a.id, "start": "2030-03-12 14:00:00", "state": "done",
        })
        self.assertEqual(payload["state"], "confirmed")  # "state" is not a bookable field
        self.assertEqual(payload["duration"], 30)

    def test_provider_day_lists_busy_times_only(self):
        self.book(start=NOW + timedelta(hours=1), branch_id=self.branch_b.id, user=self.reception_b)
        busy = self.env["careos.appointment"].with_user(self.reception).careos_provider_day(self.provider.id, "2030-03-12")
        self.assertEqual(busy, [{"start": "2030-03-12 11:00:00", "stop": "2030-03-12 11:20:00"}])

    def test_list_filters(self):
        today = self.book(start=NOW + timedelta(hours=1))
        self.book(start=NOW + timedelta(days=1), patient_id=self.patient2.id)
        List = self.env["careos.appointment"].with_user(self.reception)
        result = List.careos_list({"day": "2030-03-12"})
        self.assertEqual([r["id"] for r in result["records"]], today.ids)
        self.assertEqual(List.careos_list({"day": "2030-03-12", "state": "done"})["total"], 0)
        self.assertEqual(List.careos_list({"query": "Second Appointment"})["total"], 1)
        self.assertEqual(List.careos_list({"query": today.name})["total"], 1)
