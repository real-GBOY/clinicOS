from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW, NOW, CareosAppointmentCase
from odoo.addons.careos_queue.models.careos_queue_ticket import CareosQueueTicket

ACL_LOGGERS = ("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.models")


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestQueue(CareosAppointmentCase):
    def checked_in(self, **vals):
        appointment = self.book(**vals)
        desk = self.reception_b if appointment.branch_id == self.branch_b else self.reception
        appointment.with_user(desk).action_check_in()
        return appointment, appointment.queue_ticket_ids

    # ------------------------------------------------------------------
    # Check-in → ticket
    # ------------------------------------------------------------------

    def test_check_in_creates_waiting_ticket(self):
        appointment, ticket = self.checked_in(room_id=self.room_2.id)
        self.assertEqual(appointment.state, "checked_in")
        self.assertEqual(len(ticket), 1)
        self.assertRecordValues(ticket, [{
            "state": "waiting", "number": 1, "patient_id": self.patient.id, "provider_id": self.provider.id,
            "branch_id": self.branch_a.id, "room_id": self.room_2.id, "checked_in_at": NOW,
        }])
        self.assertEqual(str(ticket.queue_date), "2030-03-12")

    def test_ticket_numbers_per_branch_and_day(self):
        _a1, t1 = self.checked_in()
        _a2, t2 = self.checked_in(patient_id=self.patient2.id, provider_id=self.provider2.id)
        _b1, tb = self.checked_in(branch_id=self.branch_b.id, provider_id=self.provider_b.id,
                                  patient_id=self.env["careos.patient"].create({"name": "B"}).id)
        self.assertEqual((t1.number, t2.number, tb.number), (1, 2, 1))
        with freeze_time("2030-03-13 09:00:00"):
            _n, next_day = self.checked_in(start=NOW + timedelta(days=1), patient_id=self.env["careos.patient"].create({"name": "N"}).id)
        self.assertEqual(next_day.number, 1)

    def test_check_in_is_atomic(self):
        """If the queue ticket cannot be issued, the appointment is not
        checked in either."""
        appointment = self.book()
        with patch.object(CareosQueueTicket, "_careos_create_for", side_effect=UserError("Queue offline")):
            with self.assertRaises(UserError):
                appointment.action_check_in()
        self.assertEqual(appointment.state, "confirmed")
        self.assertFalse(appointment.checked_in_at)
        self.assertFalse(appointment.queue_ticket_ids)

    def test_tickets_cannot_be_created_or_edited_directly(self):
        appointment, ticket = self.checked_in()
        with self.assertRaises(UserError):
            self.env["careos.queue.ticket"].create({"appointment_id": appointment.id, "queue_date": "2030-03-12",
                                                    "number": 9, "checked_in_at": NOW})
        with self.assertRaises(UserError):
            ticket.write({"state": "done"})

    # ------------------------------------------------------------------
    # Queue workflow
    # ------------------------------------------------------------------

    def test_full_queue_flow_moves_appointment(self):
        appointment, ticket = self.checked_in()
        ticket.with_user(self.reception).action_call()
        self.assertRecordValues(ticket, [{"state": "called", "called_at": NOW, "called_by_id": self.reception.id,
                                          "room_id": self.room_1.id}])  # provider default room
        ticket.with_user(self.reception).action_start()
        self.assertEqual((ticket.state, appointment.state), ("in_consultation", "in_progress"))
        ticket.with_user(self.reception).action_complete()
        self.assertEqual((ticket.state, appointment.state), ("done", "done"))
        self.assertEqual(ticket.completed_at, NOW)

    def test_starting_from_the_appointment_moves_the_ticket(self):
        appointment, ticket = self.checked_in()
        appointment.with_user(self.doctor).action_start()
        self.assertEqual(ticket.state, "in_consultation")
        self.assertEqual(ticket.called_at, NOW)  # implicit call recorded

    def test_no_show_from_the_queue(self):
        appointment, ticket = self.checked_in()
        ticket.with_user(self.reception).action_no_show()
        self.assertEqual((ticket.state, appointment.state), ("no_show", "no_show"))

    def test_invalid_queue_transitions(self):
        _appointment, ticket = self.checked_in()
        with self.assertRaises(UserError):
            ticket.action_complete()  # not in consultation yet
        ticket.action_call()
        with self.assertRaises(UserError):
            ticket.action_call()  # already called
        ticket.action_start()
        for action in ("action_call", "action_start", "action_no_show"):
            with self.subTest(action=action), self.assertRaises(UserError):
                getattr(ticket, action)()
        ticket.action_complete()
        for action in ("action_call", "action_start", "action_complete", "action_no_show"):
            with self.subTest(action=action), self.assertRaises(UserError):
                getattr(ticket, action)()

    def test_board_orders_called_first_then_arrival(self):
        _a1, first = self.checked_in()
        with freeze_time("2030-03-12 10:05:00"):
            _a2, second = self.checked_in(patient_id=self.patient2.id, provider_id=self.provider2.id)
        second.action_call()
        board = self.env["careos.queue.ticket"].with_user(self.reception).careos_queue_board()
        self.assertEqual([t["id"] for t in board["waiting"]], [second.id, first.id])
        self.assertEqual([t["position"] for t in board["waiting"]], [1, 2])
        self.assertEqual(board["waiting"][1]["actions"], ["call", "no_show"])

    # ------------------------------------------------------------------
    # Permissions and branch isolation
    # ------------------------------------------------------------------

    @mute_logger(*ACL_LOGGERS)
    def test_nurse_calls_but_does_not_run_consultations(self):
        _appointment, ticket = self.checked_in()
        ticket.with_user(self.nurse).action_call()
        with self.assertRaises(AccessError):
            ticket.with_user(self.nurse).action_start()
        with self.assertRaises(AccessError):
            ticket.with_user(self.nurse).action_no_show()

    @mute_logger(*ACL_LOGGERS)
    def test_doctor_runs_own_queue_only(self):
        _own, own_ticket = self.checked_in()
        _other, other_ticket = self.checked_in(patient_id=self.patient2.id, provider_id=self.provider2.id)
        Ticket = self.env["careos.queue.ticket"].with_user(self.doctor)
        self.assertEqual(Ticket.search([]), own_ticket)
        own_ticket.with_user(self.doctor).action_call()
        own_ticket.with_user(self.doctor).action_start()
        own_ticket.with_user(self.doctor).action_complete()
        with self.assertRaises(AccessError):
            other_ticket.with_user(self.doctor).action_call()

    @mute_logger(*ACL_LOGGERS)
    def test_roles_without_queue_access(self):
        self.checked_in()
        for user in (self.lab, self.finance):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.env["careos.queue.ticket"].with_user(user).search([])
        _a, ticket = self.checked_in(patient_id=self.patient2.id, provider_id=self.provider2.id)
        with self.assertRaises(AccessError):
            ticket.with_user(self.manager).action_call()

    @mute_logger(*ACL_LOGGERS)
    def test_branch_isolation(self):
        _a, ticket_a = self.checked_in()
        _b, ticket_b = self.checked_in(branch_id=self.branch_b.id, provider_id=self.provider_b.id, patient_id=self.patient2.id)
        self.assertEqual(self.env["careos.queue.ticket"].with_user(self.reception).search([]), ticket_a)
        self.assertEqual(self.env["careos.queue.ticket"].with_user(self.reception_b).search([]), ticket_b)
        with self.assertRaises(AccessError):
            ticket_b.with_user(self.reception).action_call()
        board = self.env["careos.queue.ticket"].with_user(self.reception).careos_queue_board()
        self.assertEqual([t["id"] for t in board["waiting"]], ticket_a.ids)

    # ------------------------------------------------------------------
    # Timeline and dashboard integration
    # ------------------------------------------------------------------

    def test_timeline_records_queue_events(self):
        _appointment, ticket = self.checked_in()
        ticket.action_call()
        ticket.action_start()
        ticket.action_complete()
        timeline = self.patient.with_user(self.reception).careos_get_profile()["timeline"]
        titles = [e["title"] for e in timeline if e.get("kind") == "appointment"]
        self.assertEqual(titles, ["Visit completed", "Consultation started", "Patient called", "Patient checked in",
                                  "Appointment confirmed", "Appointment booked"])
        called = next(e for e in timeline if e["title"] == "Patient called")
        self.assertIn("Room 1", called["detail"])

    def test_dashboard_waiting_metric_and_panel(self):
        _a1, waiting = self.checked_in()
        _a2, consulting = self.checked_in(patient_id=self.patient2.id, provider_id=self.provider2.id)
        consulting.action_call()
        consulting.action_start()
        dashboard = self.env["careos.appointment"].with_user(self.reception).careos_reception_dashboard()
        kpis = {k["key"]: k["value"] for k in dashboard["kpis"]}
        self.assertEqual(kpis["waiting"], 1)
        self.assertEqual(kpis["in_progress"], 1)
        self.assertEqual([k["key"] for k in dashboard["kpis"]], ["booked", "arrived", "waiting", "in_progress", "done", "no_show"])
        self.assertEqual([t["id"] for t in dashboard["queue"]["waiting"]], waiting.ids)
        self.assertEqual([t["id"] for t in dashboard["queue"]["in_consultation"]], consulting.ids)

    def test_appointment_payload_exposes_ticket(self):
        appointment, ticket = self.checked_in()
        payload = appointment.careos_get_detail()
        self.assertEqual(payload["queue_ticket"]["label"], "#001")
        self.assertEqual(payload["queue_ticket"]["state_label"], "Waiting")
