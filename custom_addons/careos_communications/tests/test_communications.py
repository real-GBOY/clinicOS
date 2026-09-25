from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW, NOW, CareosAppointmentCase


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestCommunications(CareosAppointmentCase):
    def test_conversation_both_ways(self):
        self.patient._careos_post_from_patient("Can I come earlier?")
        thread = self.patient.with_user(self.reception).careos_send_message("Yes, 9:30 is free.\nSee you then.")
        self.assertEqual([m["from_patient"] for m in thread], [True, False])
        self.assertEqual(thread[1]["text"], "Yes, 9:30 is free.\nSee you then.")
        inbox = self.env["careos.communications"].with_user(self.reception).careos_inbox()
        self.assertEqual(inbox["conversations"][0]["patient"]["id"], self.patient.id)
        self.assertFalse(inbox["conversations"][0]["needs_reply"])

    def test_patient_message_notifies_front_desk_and_needs_reply(self):
        self.patient._careos_post_from_patient("Is my result ready?")
        titles = [n["title"] for n in self.env["careos.notification"].with_user(self.reception).careos_inbox()["items"]]
        self.assertIn("New message — Appointment Patient", titles)
        inbox = self.env["careos.communications"].with_user(self.reception).careos_inbox()
        self.assertTrue(inbox["conversations"][0]["needs_reply"])

    def test_notes_are_not_patient_messages(self):
        self.patient.with_user(self.reception).careos_post_note("Internal: difficult to reach by phone")
        self.assertEqual(self.patient.with_user(self.reception).careos_get_conversation(), [])

    def test_messages_are_escaped_and_required(self):
        thread = self.patient.with_user(self.reception).careos_send_message("<b>bold</b>")
        self.assertEqual(thread[0]["text"], "<b>bold</b>")
        with self.assertRaises(ValidationError):
            self.patient.with_user(self.reception).careos_send_message("  ")

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_inbox_roles(self):
        for user in (self.lab, self.finance):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.env["careos.communications"].with_user(user).careos_inbox()

    def test_reminders_follow_the_appointment(self):
        self.patient.email = "patient@example.com"
        appointment = self.book(start=NOW + timedelta(days=2))
        reminder = appointment.reminder_ids
        self.assertEqual((reminder.state, reminder.channel), ("scheduled", "email"))
        self.assertEqual(reminder.scheduled_at, appointment.start - timedelta(hours=24))
        appointment.with_user(self.reception).careos_reschedule({"start": NOW + timedelta(days=3)})
        self.assertEqual(sorted(appointment.reminder_ids.mapped("state")), ["cancelled", "scheduled"])
        appointment.action_cancel("Patient request")
        self.assertFalse(appointment.reminder_ids.filtered(lambda r: r.state == "scheduled"))

    def test_reminder_delivery(self):
        self.patient.email = "patient@example.com"
        appointment = self.book(start=NOW + timedelta(hours=5))
        reminder = appointment.reminder_ids
        self.assertEqual(reminder.scheduled_at, NOW)  # less than 24h away: due now
        with patch("odoo.addons.mail.models.mail_mail.MailMail.send") as send:
            self.env["careos.reminder"]._careos_cron_send()
        self.assertTrue(send.called)
        self.assertEqual(reminder.state, "sent")
        self.assertTrue(any("Reminder" in m["text"] for m in self.patient.careos_get_conversation()))

    def test_reminder_without_provider_fails_visibly(self):
        appointment = self.book(start=NOW + timedelta(hours=5), patient_id=self.patient2.id)  # no e-mail
        reminder = appointment.reminder_ids
        self.assertEqual(reminder.channel, "sms")
        self.env["careos.reminder"]._careos_cron_send()
        self.assertEqual(reminder.state, "failed")
        self.assertIn("No SMS provider", reminder.error)
