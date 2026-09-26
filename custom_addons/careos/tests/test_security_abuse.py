"""Security abuse tests: assume the frontend does not exist and attack the backend.

Every public ``careos_*`` method is reachable through RPC with arbitrary
arguments, so these tests call the backend directly the way a crafted
request would: other people's record IDs, other branches, forged states,
role escalation, restricted fields, and invalid amounts. The HTTP class
repeats the most important attacks over real JSON-RPC.
"""
import json
from datetime import timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tests.common import JsonRpcException
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW, NOW
from odoo.addons.careos_finance.tests.common import CareosBillingCase

QUIET = ("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.models", "odoo.http")


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos", "careos_security")
class TestSecurityAbuse(CareosBillingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def portal_user(login, patient):
            user = new_test_user(cls.env, login=login, groups="base.group_portal", partner_id=patient._careos_partner().id)
            patient.sudo().portal_user_id = user
            return user

        cls.portal_one = portal_user("abuse_portal_one", cls.patient)
        cls.portal_two = portal_user("abuse_portal_two", cls.patient2)

    # ------------------------------------------------------------------
    # Clinical record
    # ------------------------------------------------------------------

    @mute_logger(*QUIET)
    def test_front_desk_cannot_reach_the_clinical_record(self):
        appointment, encounter = self.visit()
        for call in (
            lambda: self.env["careos.encounter"].with_user(self.reception).search_read([], ["notes"]),
            lambda: encounter.with_user(self.reception).careos_get_workspace(),
            lambda: encounter.with_user(self.reception).careos_save({"notes": "forged"}),
            lambda: self.env["careos.diagnosis"].with_user(self.reception).create(
                {"encounter_id": encounter.id, "code": "Z00", "description": "forged"}),
        ):
            with self.assertRaises(AccessError):
                call()

    @mute_logger(*QUIET)
    def test_nurse_writes_vitals_only(self):
        _appointment, encounter = self.visit()
        encounter.with_user(self.nurse).careos_save({"bp_systolic": 120, "bp_diastolic": 80})
        for vals in ({"notes": "forged"}, {"plan": "forged"}, {"bp_systolic": 118, "chief_complaint": "smuggled"}):
            with self.assertRaises(AccessError):
                encounter.with_user(self.nurse).careos_save(vals)
        with self.assertRaises(AccessError):
            encounter.with_user(self.nurse).action_complete()

    @mute_logger(*QUIET)
    def test_doctor_cannot_use_another_doctors_record_ids(self):
        _appointment, encounter = self.visit()  # treated by self.doctor
        intruder = encounter.with_user(self.doctor2)
        for call in (
            lambda: intruder.careos_get_workspace(),
            lambda: intruder.careos_save({"notes": "forged"}),
            lambda: intruder.careos_new_prescription(),
            lambda: intruder.careos_order_lab(self.env.ref("careos_laboratory.test_cbc").ids),
            lambda: intruder.action_complete(),
        ):
            with self.assertRaises(AccessError):
                call()

    @mute_logger(*QUIET)
    def test_workflow_states_cannot_be_forged(self):
        appointment, encounter = self.visit()
        rx = self.prescribe(encounter)
        order_id = encounter.with_user(self.doctor).careos_order_lab(self.env.ref("careos_laboratory.test_glucose").ids)
        order = self.env["careos.lab.order"].search([("encounter_id", "=", encounter.id)], limit=1)
        self.assertTrue(order_id or order)
        for record, user, vals in (
            (appointment, self.reception, {"state": "done"}),
            (encounter, self.doctor, {"state": "done"}),
            (rx, self.doctor, {"state": "dispensed"}),
            (order, self.lab, {"state": "verified"}),
            (appointment.queue_ticket_ids, self.reception, {"state": "done"}),
        ):
            with self.subTest(model=record._name), self.assertRaises(UserError):
                record.with_user(user).write(vals)
        self.assertEqual((appointment.state, encounter.state, rx.state), ("in_progress", "open", "draft"))

    # ------------------------------------------------------------------
    # Branch isolation with guessed IDs
    # ------------------------------------------------------------------

    @mute_logger(*QUIET)
    def test_other_branch_ids_are_refused(self):
        appointment = self.completed_visit()
        move_id = self.env["careos.billing"].with_user(self.reception).careos_create_invoice(appointment.id)
        other_desk = self.env["careos.billing"].with_user(self.reception_b)
        for call in (
            lambda: other_desk.careos_visit_billing(appointment.id),
            lambda: other_desk.careos_invoice_detail(move_id),
            lambda: other_desk.careos_post(move_id),
            lambda: other_desk.careos_register_payment(move_id, 10, "cash"),
            lambda: appointment.with_user(self.reception_b).action_cancel("forged"),
            lambda: self.env["careos.appointment"].with_user(self.reception_b).browse(appointment.id).read(["state"]),
        ):
            with self.assertRaises(AccessError):
                call()

    # ------------------------------------------------------------------
    # Role escalation and administration
    # ------------------------------------------------------------------

    @mute_logger(*QUIET)
    def test_role_escalation_is_refused(self):
        invite = {"name": "Mallory", "email": "mallory@example.com", "roles": ["admin"], "branch_ids": self.branch_a.ids}
        for user in (self.reception, self.doctor, self.manager, self.finance):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.env["careos.staff"].with_user(user).careos_staff_invite(invite)
        with self.assertRaises(AccessError):
            self.env["careos.staff"].with_user(self.manager).careos_staff_save(self.manager.id, {
                "name": self.manager.name, "email": self.manager.login, "roles": ["manager", "admin"],
                "branch_ids": self.branch_a.ids})
        # Writing one's own groups through the ORM is refused by Odoo itself.
        with self.assertRaises(AccessError):
            self.reception.with_user(self.reception).write(
                {"group_ids": [(4, self.env.ref("careos_base.group_careos_admin").id)]})
        self.assertFalse(self.reception.has_group("careos_base.group_careos_admin"))
        for call in (
            lambda: self.env["careos.setup"].with_user(self.manager).careos_setup_save("organization", {"name": "Pwned"}),
            lambda: self.env["careos.ai"].with_user(self.doctor).careos_configure(True, "sk-forged"),
            lambda: self.env["careos.staff.log"].with_user(self.careos_admin).create(
                {"user_id": self.reception.id, "actor_id": self.careos_admin.id, "summary": "forged"}),
        ):
            with self.assertRaises(AccessError):
                call()

    @mute_logger(*QUIET)
    def test_restricted_fields_are_not_readable(self):
        patient = self.patient.with_user(self.reception)
        for field in ("blood_type", "condition_ids"):
            with self.subTest(field=field), self.assertRaises(AccessError):
                patient.read([field])
        with self.assertRaises(AccessError):
            self.env["careos.patient"].with_user(self.reception).search_read([("blood_type", "=", "O+")], ["name"])

    # ------------------------------------------------------------------
    # Money
    # ------------------------------------------------------------------

    @mute_logger(*QUIET)
    def test_billing_abuse(self):
        appointment = self.completed_visit()
        Billing = self.env["careos.billing"]
        with self.assertRaises(AccessError):
            Billing.with_user(self.doctor).careos_create_invoice(appointment.id)
        with self.assertRaises(AccessError):
            Billing.with_user(self.nurse).careos_invoice_list()
        move_id = Billing.with_user(self.reception).careos_create_invoice(appointment.id)
        Billing.with_user(self.reception).careos_post(move_id)
        balance = self.env["account.move"].browse(move_id).amount_residual
        for amount in (0, -50, balance + 1):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                Billing.with_user(self.reception).careos_register_payment(move_id, amount, "cash")
        with self.assertRaises(AccessError):  # only finance refunds
            Billing.with_user(self.reception).careos_refund(move_id, "forged")
        with self.assertRaises(ValidationError):  # a refund needs a reason
            Billing.with_user(self.finance_user).careos_refund(move_id, "  ")
        with self.assertRaises(UserError):  # nothing left to bill twice
            Billing.with_user(self.reception).careos_create_invoice(appointment.id)

    # ------------------------------------------------------------------
    # Pharmacy, stock and laboratory
    # ------------------------------------------------------------------

    @mute_logger(*QUIET)
    def test_pharmacy_and_stock_abuse(self):
        _appointment, encounter = self.visit()
        rx = self.prescribe(encounter)
        with self.assertRaises(AccessError):
            rx.with_user(self.pharmacist).action_issue()
        rx.with_user(self.doctor).action_issue()
        with self.assertRaises(AccessError):
            rx.with_user(self.doctor).action_dispense()
        with self.assertRaises(UserError):  # issued prescriptions are frozen
            rx.line_ids.with_user(self.doctor).write({"quantity": 50})
        Inventory = self.env["careos.inventory"]
        for user in (self.reception, self.doctor, self.manager):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                Inventory.with_user(user).careos_receive(self.lisinopril.id, 1000)
        not_an_item = self.env["product.product"].create({"name": "Office chair", "type": "consu"})
        with self.assertRaises(ValidationError):
            Inventory.with_user(self.pharmacist).careos_receive(not_an_item.id, 5)

    @mute_logger(*QUIET)
    def test_laboratory_abuse(self):
        _appointment, encounter = self.visit()
        encounter.with_user(self.doctor).careos_order_lab(self.env.ref("careos_laboratory.test_glucose").ids)
        order = self.env["careos.lab.order"].search([("encounter_id", "=", encounter.id)], limit=1)
        with self.assertRaises(AccessError):
            self.env["careos.lab.order"].with_user(self.nurse).create({"encounter_id": encounter.id})
        with self.assertRaises(UserError):  # results only while processing
            order.with_user(self.lab).careos_save_results({str(order.result_ids[:1].id): 90})
        order.with_user(self.lab).action_collect()
        order.with_user(self.lab).action_process()
        with self.assertRaises(AccessError):
            order.with_user(self.doctor).careos_save_results({str(order.result_ids[:1].id): 90})
        with self.assertRaises(UserError):  # verify before results
            order.with_user(self.lab).action_verify()

    # ------------------------------------------------------------------
    # Patient portal
    # ------------------------------------------------------------------

    @mute_logger(*QUIET)
    def test_portal_guessing_and_crafted_arguments(self):
        other = self.book(patient_id=self.patient2.id, start=NOW + timedelta(days=1, hours=2))
        Portal = self.env["careos.portal"].with_user(self.portal_one)
        with self.assertRaises(AccessError):  # someone else's appointment id
            Portal.careos_portal_reschedule(other.id, "please")
        with self.assertRaises(ValidationError):  # doctor from another branch
            Portal.careos_portal_book(self.provider_b.id, self.type_consult.id, str(NOW + timedelta(days=2)))
        with self.assertRaises(ValidationError):  # made-up visit type
            Portal.careos_portal_book(self.provider.id, 999999, str(NOW + timedelta(days=2)))
        with self.assertRaises(ValidationError):  # garbage date
            Portal.careos_portal_book(self.provider.id, self.type_consult.id, "not-a-date")
        with self.assertRaises(AccessError):  # staff-only preview
            Portal.careos_preview(self.patient2.id)
        for model in ("careos.patient", "careos.appointment", "careos.encounter"):
            with self.subTest(model=model), self.assertRaises(AccessError):
                self.env[model].with_user(self.portal_one).search_read([], ["id"])
        # Odoo lets portal users read their *own* invoices (portal invoice page);
        # another patient's invoice must stay invisible, even by id.
        appointment2, encounter2 = self.visit(patient_id=self.patient2.id)
        self.diagnose(encounter2)
        encounter2.with_user(self.doctor).action_complete()
        move_id = self.env["careos.billing"].with_user(self.reception).careos_create_invoice(appointment2.id)
        self.env["careos.billing"].with_user(self.reception).careos_post(move_id)
        self.assertNotIn(move_id, self.env["account.move"].with_user(self.portal_one).search([]).ids)
        self.assertIn(move_id, self.env["account.move"].with_user(self.portal_two).search([]).ids)
        with self.assertRaises(AccessError):
            self.env["account.move"].with_user(self.portal_one).browse(move_id).read(["amount_total"])
        data = Portal.careos_portal_data()
        self.assertNotIn(other.id, [a["id"] for a in data["appointments"]])
        self.assertNotIn(self.patient2.name, json.dumps(data, default=str))

    @mute_logger(*QUIET)
    def test_ai_suggestions_belong_to_their_author(self):
        self.env["ir.config_parameter"].sudo().set_param("careos_ai.enabled", "1")
        _appointment, encounter = self.visit()
        suggestion = self.env["careos.ai.suggestion"].sudo().create({
            "kind": "encounter", "res_model": "careos.encounter", "res_id": encounter.id,
            "user_id": self.doctor.id, "output": {"plan": "forged plan"},
        })
        AI = self.env["careos.ai"]
        with self.assertRaises(AccessError):
            AI.with_user(self.doctor2).careos_apply_note(suggestion.id, ["plan"])
        with self.assertRaises(AccessError):
            AI.with_user(self.reception).careos_dismiss(suggestion.id)
        with self.assertRaises(AccessError):  # front desk cannot send a chart to the model
            AI.with_user(self.reception).careos_assist("encounter", encounter.id)
        self.assertFalse(encounter.plan)


@tagged("post_install", "-at_install", "careos", "careos_security")
class TestSecurityAbuseHttp(HttpCase):
    """The same attacks over real JSON-RPC, as a logged-in attacker would send them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.branch = env["careos.branch"].create({"name": "RPC Branch", "code": "RPC", "timezone": "UTC"})
        cls.other_branch = env["careos.branch"].create({"name": "RPC Other", "code": "RPO", "timezone": "UTC"})
        vals = {"careos_branch_ids": [(6, 0, cls.branch.ids)], "careos_branch_id": cls.branch.id}
        new_test_user(env, login="rpc_reception", groups="careos_base.group_careos_reception", **vals)
        new_test_user(env, login="rpc_doctor", groups="careos_base.group_careos_doctor", **vals)
        cls.patient = env["careos.patient"].create({"name": "Rpc Patient", "branch_id": cls.branch.id, "email": "rpc@example.com"})
        cls.victim = env["careos.patient"].create({"name": "Rpc Victim", "branch_id": cls.branch.id})
        portal = new_test_user(env, login="rpc_portal", groups="base.group_portal", partner_id=cls.patient._careos_partner().id)
        cls.patient.portal_user_id = portal
        provider = env["careos.provider"].create({"name": "Dr. Rpc", "branch_ids": [(6, 0, cls.branch.ids)]})
        cls.other_provider = env["careos.provider"].create({"name": "Dr. Elsewhere", "branch_ids": [(6, 0, cls.other_branch.ids)]})
        cls.type = env.ref("careos_appointments.type_consultation")
        start = (env["careos.branch"].browse(cls.branch.id)._careos_today() + timedelta(days=3))
        cls.victim_appointment = env["careos.appointment"].create({
            "patient_id": cls.victim.id, "provider_id": provider.id, "branch_id": cls.branch.id,
            "type_id": cls.type.id, "start": f"{start} 10:00:00",
        })

    def call_kw(self, model, method, args=None, kwargs=None):
        return self.make_jsonrpc_request(f"/web/dataset/call_kw/{model}/{method}", {
            "model": model, "method": method, "args": args or [], "kwargs": kwargs or {},
        })

    def assertRpcError(self, error_name, call):
        with self.assertRaises(JsonRpcException) as caught:
            call()
        self.assertIn(error_name, str(caught.exception))

    @mute_logger(*QUIET)
    def test_private_methods_are_not_callable(self):
        self.authenticate("rpc_reception", "rpc_reception")
        self.assertRpcError("AccessError", lambda: self.call_kw(
            "careos.patient", "_careos_post_from_patient", [[self.victim.id], "forged message"]))
        self.assertRpcError("AccessError", lambda: self.call_kw(
            "careos.staff", "_careos_create_staff", [{"name": "x", "email": "x@example.com", "roles": ["admin"]}]))

    @mute_logger(*QUIET)
    def test_role_limits_hold_over_rpc(self):
        self.authenticate("rpc_reception", "rpc_reception")
        self.assertRpcError("AccessError", lambda: self.call_kw("careos.encounter", "search_read", [[], ["notes"]]))
        self.assertRpcError("AccessError", lambda: self.call_kw("careos.staff", "careos_staff_invite", [{
            "name": "Mallory", "email": "mallory@example.com", "roles": ["admin"], "branch_ids": [self.branch.id]}]))
        self.assertRpcError("AccessError", lambda: self.call_kw(
            "careos.patient", "read", [[self.patient.id], ["blood_type"]]))

    @mute_logger(*QUIET)
    def test_portal_attacks_over_http(self):
        self.authenticate("rpc_portal", "rpc_portal")
        data = self.make_jsonrpc_request("/careos/portal/data")
        self.assertEqual(data["patient"]["name"], "Rpc Patient")
        self.assertRpcError("AccessError", lambda: self.make_jsonrpc_request(
            "/careos/portal/reschedule", {"appointment_id": self.victim_appointment.id}))
        self.assertRpcError("ValidationError", lambda: self.make_jsonrpc_request("/careos/portal/book", {
            "provider_id": self.other_provider.id, "type_id": self.type.id, "start": "2099-01-01 10:00:00"}))
        self.assertRpcError("AccessError", lambda: self.call_kw("careos.patient", "search_read", [[], ["name"]]))
        self.assertRpcError("AccessError", lambda: self.call_kw(
            "careos.portal", "careos_preview", [self.victim.id]))

    @mute_logger(*QUIET)
    def test_anonymous_requests_are_rejected(self):
        self.assertRpcError("SessionExpired", lambda: self.make_jsonrpc_request("/careos/portal/data"))
        self.assertRpcError("SessionExpired", lambda: self.call_kw("careos.patient", "search_read", [[], ["name"]]))
