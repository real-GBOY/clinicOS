from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW
from .common import CareosBillingCase

ACL_LOGGERS = ("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.models")


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestBilling(CareosBillingCase):
    def test_invoice_bills_everything_once(self):
        appointment = self.completed_visit()
        Billing = self.env["careos.billing"].with_user(self.reception)
        pending = Billing.careos_visit_billing(appointment.id)
        self.assertEqual(pending["pending_total"], 450 + 80 + 250)
        move = self.env["account.move"].browse(Billing.careos_create_invoice(appointment.id))
        self.assertEqual(move.move_type, "out_invoice")
        self.assertEqual(move.partner_id, self.patient.partner_id)
        self.assertEqual(sorted(move.invoice_line_ids.mapped("price_unit")), [80, 250, 450])
        self.assertEqual(Billing.careos_visit_billing(appointment.id)["pending"], [])
        with self.assertRaises(UserError):
            Billing.careos_create_invoice(appointment.id)

    def test_post_and_partial_then_full_payment(self):
        appointment = self.completed_visit()
        Billing = self.env["careos.billing"].with_user(self.reception)
        move_id = Billing.careos_create_invoice(appointment.id)
        self.assertEqual(Billing.careos_invoice_detail(move_id)["status"], "draft")
        with self.assertRaises(UserError):
            Billing.careos_register_payment(move_id, 100)  # not issued yet
        detail = Billing.careos_post(move_id)
        self.assertEqual(detail["status"], "pending")
        detail = Billing.careos_register_payment(move_id, 400, "card")
        self.assertEqual((detail["status"], detail["balance"]), ("partial", 380))
        with self.assertRaises(ValidationError):
            Billing.careos_register_payment(move_id, 1000)  # more than the balance
        detail = Billing.careos_register_payment(move_id, 380, "cash")
        self.assertEqual(detail["status"], "paid")
        self.assertEqual(len(detail["payments"]), 2)
        self.assertEqual(self.patient.with_user(self.reception).careos_get_profile()["balance_due"], 0)

    @mute_logger(*ACL_LOGGERS)
    def test_roles(self):
        appointment = self.completed_visit()
        with self.assertRaises(AccessError):
            self.env["careos.billing"].with_user(self.doctor).careos_create_invoice(appointment.id)
        move_id = self.env["careos.billing"].with_user(self.reception).careos_create_invoice(appointment.id)
        self.env["careos.billing"].with_user(self.reception).careos_post(move_id)
        with self.assertRaises(AccessError):
            self.env["careos.billing"].with_user(self.reception).careos_refund(move_id, "Complaint")
        detail = self.env["careos.billing"].with_user(self.finance_user).careos_refund(move_id, "Complaint")
        self.assertEqual(detail["status"], "refunded")
        self.assertTrue(detail["credit_note"])
        with self.assertRaises(AccessError):
            self.env["careos.billing"].with_user(self.manager).careos_register_payment(move_id, 10)
        self.assertTrue(self.env["careos.billing"].with_user(self.manager).careos_invoice_detail(move_id))
        with self.assertRaises(AccessError):
            self.env["careos.billing"].with_user(self.lab).careos_invoice_detail(move_id)

    @mute_logger(*ACL_LOGGERS)
    def test_branch_isolation(self):
        appointment = self.completed_visit()
        move_id = self.env["careos.billing"].with_user(self.reception).careos_create_invoice(appointment.id)
        with self.assertRaises(AccessError):
            self.env["careos.billing"].with_user(self.reception_b).careos_invoice_detail(move_id)
        self.assertEqual(self.env["careos.billing"].with_user(self.reception_b).careos_invoice_list(), [])

    def test_search_finds_invoices_for_front_desk(self):
        appointment = self.completed_visit()
        Billing = self.env["careos.billing"].with_user(self.reception)
        move_id = Billing.careos_create_invoice(appointment.id)
        Billing.careos_post(move_id)
        name = self.env["account.move"].browse(move_id).name
        results = self.env["careos.search"].with_user(self.reception).careos_global_search(name)
        self.assertIn(("account.move", move_id), [(r["model"], r["id"]) for r in results])
        doctor_results = self.env["careos.search"].with_user(self.doctor).careos_global_search(name)
        self.assertFalse([r for r in doctor_results if r["model"] == "account.move"])
