from datetime import timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW, NOW
from odoo.addons.careos_finance.tests.common import CareosBillingCase


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestPortal(CareosBillingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.patient.email = "patient.one@example.com"

        def portal_user(login, patient):
            user = new_test_user(cls.env, login=login, groups="base.group_portal", partner_id=patient._careos_partner().id)
            patient.sudo().write({"portal_user_id": user.id})
            return user

        cls.portal_one = portal_user("portal_one", cls.patient)
        cls.portal_two = portal_user("portal_two", cls.patient2)

    def portal(self, user):
        return self.env["careos.portal"].with_user(user)

    def test_payload_shows_only_released_information(self):
        appointment = self.completed_visit()
        Billing = self.env["careos.billing"].with_user(self.reception)
        move_id = Billing.careos_create_invoice(appointment.id)
        Billing.careos_post(move_id)
        data = self.portal(self.portal_one).careos_portal_data()
        self.assertEqual(data["patient"]["id"], self.patient.id)
        self.assertEqual([p["med"] for p in data["prescriptions"]], ["Lisinopril 10mg"])
        self.assertEqual(data["lab_results"], [])  # ordered but not verified yet
        self.assertEqual(data["balance_due"], 780)
        self.assertTrue(data["invoices"][0]["pay_url"])
        order = appointment.encounter_ids.lab_order_ids
        lab = order.with_user(self.lab)
        lab.action_collect()
        lab.action_process()
        lab.action_submit_results({str(r.id): 90 for r in order.result_ids})
        self.assertEqual(self.portal(self.portal_one).careos_portal_data()["lab_results"], [])  # not verified
        lab.action_verify()
        released = self.portal(self.portal_one).careos_portal_data()["lab_results"]
        self.assertEqual(len(released), 1)
        self.assertTrue(released[0]["is_new"])

    def test_patients_are_isolated(self):
        appointment = self.book(start=NOW + timedelta(days=1))
        self.assertEqual(self.portal(self.portal_two).careos_portal_data()["appointments"], [])
        with self.assertRaises(AccessError):
            self.portal(self.portal_two).careos_portal_reschedule(appointment.id)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_portal_users_have_no_direct_model_access(self):
        with self.assertRaises(AccessError):
            self.env["careos.patient"].with_user(self.portal_one).search([])
        with self.assertRaises(AccessError):
            self.env["careos.appointment"].with_user(self.portal_one).search([])
        staff = new_test_user(self.env, login="no_patient", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.portal(staff).careos_portal_data()

    def test_messages_and_reschedule_requests_reach_the_front_desk(self):
        appointment = self.book(start=NOW + timedelta(days=2))
        self.portal(self.portal_one).careos_portal_message("Hello clinic")
        data = self.portal(self.portal_one).careos_portal_reschedule(appointment.id, "Mornings please")
        self.assertEqual([m["from_patient"] for m in data["messages"]], [True, True])
        self.assertIn("reschedule", data["messages"][-1]["text"])
        inbox = self.env["careos.communications"].with_user(self.reception).careos_inbox()
        self.assertTrue(inbox["conversations"][0]["needs_reply"])

    def test_booking_request_creates_a_draft_for_the_front_desk(self):
        options = self.portal(self.portal_one).careos_portal_booking_options("2030-03-13")
        self.assertIn(self.provider.id, [p["id"] for p in options["providers"]])
        self.patient.branch_id = self.branch_a
        data = self.portal(self.portal_one).careos_portal_book(self.provider.id, self.type_follow_up.id, "2030-03-13 09:00:00")
        request = self.env["careos.appointment"].search([("patient_id", "=", self.patient.id), ("state", "=", "draft")])
        self.assertEqual(len(request), 1)
        self.assertEqual(data["next_appointment"]["state_label"], "Requested")
        titles = [n["title"] for n in self.env["careos.notification"].with_user(self.reception).careos_inbox()["items"]]
        self.assertIn(f"Appointment request — {self.patient.name}", titles)
        with self.assertRaises(ValidationError):
            self.portal(self.portal_one).careos_portal_book(self.provider.id, self.type_follow_up.id, "2030-03-01 09:00:00")

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_staff_preview_and_invitation(self):
        preview = self.env["careos.portal"].with_user(self.reception).careos_preview(self.patient.id)
        self.assertTrue(preview["preview"])
        with self.assertRaises(AccessError):
            self.env["careos.portal"].with_user(self.lab).careos_preview(self.patient.id)
        with self.assertRaises(ValidationError):
            self.patient2.with_user(self.reception).careos_invite_portal()  # no e-mail
        self.patient2.email = "patient.two.new@example.com"
        self.patient2.sudo().portal_user_id = False
        profile = self.patient2.with_user(self.reception).careos_invite_portal()
        self.assertTrue(profile["portal"]["active"])
        self.assertTrue(self.patient2.sudo().portal_user_id.share)
        with self.assertRaises(AccessError):
            self.patient.with_user(self.doctor).careos_invite_portal()
