from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW
from odoo.addons.careos_clinical.tests.common import CareosVisitCase

ACL_LOGGERS = ("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.models")


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestLaboratory(CareosVisitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lipid = cls.env.ref("careos_laboratory.test_lipid")
        cls.glucose = cls.env.ref("careos_laboratory.test_glucose")

    def order(self, tests=None):
        _appointment, encounter = self.visit()
        order_id = encounter.with_user(self.doctor).careos_order_lab((tests or self.lipid).ids)
        return self.env["careos.lab.order"].browse(order_id)

    def values(self, order, **by_name):
        return {str(r.id): by_name[r.parameter_id.name] for r in order.result_ids}

    def test_full_lifecycle(self):
        order = self.order()
        self.assertEqual(order.state, "ordered")
        self.assertEqual(len(order.result_ids), 4)  # one row per lipid parameter
        lab = order.with_user(self.lab)
        lab.action_collect()
        lab.action_process()
        lab.action_submit_results(self.values(order, **{"Total Cholesterol": 240, "LDL": 150, "HDL": 45, "Triglycerides": 120}))
        self.assertEqual(order.state, "result_entered")
        self.assertTrue(order.has_abnormal)
        flags = {r.parameter_id.name: r.flag for r in order.result_ids}
        self.assertEqual(flags, {"Total Cholesterol": "high", "LDL": "high", "HDL": "normal", "Triglycerides": "normal"})
        lab.action_verify()
        order.with_user(self.doctor).action_review()
        self.assertEqual(order.state, "completed")
        self.assertEqual((order.verified_by_id, order.reviewed_by_id), (self.lab, self.doctor))

    def test_results_required_and_locked(self):
        order = self.order(self.glucose)
        lab = order.with_user(self.lab)
        lab.action_collect()
        lab.action_process()
        with self.assertRaises(UserError):
            lab.action_submit_results()
        lab.action_submit_results(self.values(order, **{"Fasting glucose": 92}))
        with self.assertRaises(UserError):
            lab.careos_save_results(self.values(order, **{"Fasting glucose": 150}))

    def test_invalid_transitions(self):
        order = self.order()
        with self.assertRaises(UserError):
            order.with_user(self.lab).action_process()  # not collected yet
        with self.assertRaises(UserError):
            order.with_user(self.lab).action_verify()

    @mute_logger(*ACL_LOGGERS)
    def test_roles(self):
        _appointment, encounter = self.visit()
        with self.assertRaises(AccessError):
            encounter.with_user(self.nurse).careos_order_lab(self.lipid.ids)
        order = self.env["careos.lab.order"].browse(encounter.with_user(self.doctor).careos_order_lab(self.glucose.ids))
        order.with_user(self.nurse).action_collect()  # nurses may collect samples
        with self.assertRaises(AccessError):
            order.with_user(self.nurse).action_process()
        with self.assertRaises(AccessError):
            order.with_user(self.reception).read(["state"])
        with self.assertRaises(AccessError):
            order.with_user(self.doctor).action_process()

    def test_doctor_notified_and_dashboard(self):
        order = self.order(self.glucose)
        lab = order.with_user(self.lab)
        lab.action_collect()
        lab.action_process()
        lab.action_submit_results(self.values(order, **{"Fasting glucose": 130}))
        inbox = self.env["careos.notification"].with_user(self.doctor).careos_inbox()
        self.assertTrue(any(n["title"].startswith("Lab result ready") and n["kind"] == "danger" for n in inbox["items"]))
        dashboard = self.env["careos.appointment"].with_user(self.doctor).careos_doctor_dashboard()
        self.assertEqual([o["id"] for o in dashboard["panels"]["lab"]], order.ids)

    def test_patient_views(self):
        order = self.order(self.glucose)
        results = self.patient.with_user(self.doctor).careos_get_lab_results()
        self.assertEqual(results[0]["id"], order.id)
        self.assertIn("Lab order placed", [e["title"] for e in self.patient.with_user(self.doctor).careos_get_profile()["timeline"]])
        self.assertFalse(self.patient.with_user(self.reception).careos_get_profile()["lab_access"])
