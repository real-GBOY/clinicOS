from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW
from odoo.addons.careos_clinical.tests.common import CareosVisitCase

ACL_LOGGERS = ("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.models")


class CareosPharmacyCase(CareosVisitCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].create({"name": "Branch A store", "code": "BRA"})
        cls.branch_a.warehouse_id = cls.warehouse
        Product = cls.env["product.product"]
        cls.lisinopril = Product.create({"name": "Lisinopril 10mg (30 tabs)", "type": "consu", "is_storable": True,
                                         "careos_item_type": "medication", "careos_strength": "10mg", "list_price": 250,
                                         **cls._no_tax()})
        cls.amoxicillin = Product.create({"name": "Amoxicillin 500mg (21 caps)", "type": "consu", "is_storable": True,
                                          "careos_item_type": "medication", "list_price": 95, **cls._no_tax()})
        Inventory = cls.env["careos.inventory"]
        Inventory._careos_demo_receive(cls.warehouse, cls.lisinopril, 10, None, None)
        Inventory._careos_demo_receive(cls.warehouse, cls.amoxicillin, 1, None, None)

    @classmethod
    def _no_tax(cls):
        # Without accounting installed products have no tax field.
        return {"taxes_id": [(5, 0, 0)]} if "taxes_id" in cls.env["product.product"]._fields else {}

    def prescribe(self, encounter, product=None, quantity=1):
        rx_id = encounter.with_user(self.doctor).careos_new_prescription()
        rx = self.env["careos.prescription"].browse(rx_id)
        self.env["careos.prescription.line"].with_user(self.doctor).create({
            "prescription_id": rx.id, "product_id": (product or self.lisinopril).id, "dose": "10mg",
            "frequency": "Once daily", "duration_days": 30, "quantity": quantity,
        })
        return rx


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestPrescriptions(CareosPharmacyCase):
    def stock(self, product):
        return product.with_context(warehouse_id=self.warehouse.id).qty_available

    def test_full_lifecycle_moves_stock(self):
        _appointment, encounter = self.visit()
        rx = self.prescribe(encounter, quantity=2)
        self.assertEqual(rx.state, "draft")
        rx.with_user(self.doctor).action_issue()
        self.assertEqual(rx.state, "issued")
        rx.with_user(self.pharmacist).action_dispense()
        self.assertEqual(rx.state, "dispensed")
        self.assertEqual(rx.dispensed_by_id, self.pharmacist)
        self.assertEqual(rx.picking_id.state, "done")
        self.assertEqual(self.stock(self.lisinopril), 8)
        rx.with_user(self.pharmacist).action_complete()
        self.assertEqual(rx.state, "completed")

    def test_insufficient_stock_blocks_dispensing(self):
        _appointment, encounter = self.visit()
        rx = self.prescribe(encounter, product=self.amoxicillin, quantity=3)
        rx.with_user(self.doctor).action_issue()
        with self.assertRaises(UserError):
            rx.with_user(self.pharmacist).action_dispense()
        self.assertEqual(rx.state, "issued")
        self.assertEqual(self.stock(self.amoxicillin), 1)

    def test_issue_requires_lines_and_locks_them(self):
        _appointment, encounter = self.visit()
        rx = self.env["careos.prescription"].browse(encounter.with_user(self.doctor).careos_new_prescription())
        with self.assertRaises(UserError):
            rx.with_user(self.doctor).action_issue()
        self.env["careos.prescription.line"].with_user(self.doctor).create({
            "prescription_id": rx.id, "product_id": self.lisinopril.id, "dose": "10mg", "frequency": "Daily", "duration_days": 30})
        rx.with_user(self.doctor).action_issue()
        with self.assertRaises(UserError):
            rx.line_ids.with_user(self.doctor).write({"dose": "20mg"})

    def test_new_prescription_reuses_the_draft(self):
        _appointment, encounter = self.visit()
        first = encounter.with_user(self.doctor).careos_new_prescription()
        self.assertEqual(encounter.with_user(self.doctor).careos_new_prescription(), first)

    def test_allergy_warning(self):
        _appointment, encounter = self.visit()
        rx = self.prescribe(encounter, product=self.amoxicillin)
        self.assertFalse(rx._careos_allergy_warnings())  # "amoxicillin" does not contain "penicillin"
        self.env["careos.patient.allergy"].create({"patient_id": self.patient.id, "allergen": "Amoxicillin"})
        self.assertTrue(rx._careos_allergy_warnings())

    @mute_logger(*ACL_LOGGERS)
    def test_roles(self):
        _appointment, encounter = self.visit()
        with self.assertRaises(AccessError):
            self.env["careos.prescription"].with_user(self.nurse).create({"encounter_id": encounter.id})
        rx = self.prescribe(encounter)
        with self.assertRaises(AccessError):
            rx.with_user(self.pharmacist).action_issue()
        rx.with_user(self.doctor).action_issue()
        with self.assertRaises(AccessError):
            rx.with_user(self.doctor).action_dispense()
        with self.assertRaises(AccessError):
            rx.with_user(self.reception).read(["state"])
        self.assertEqual(rx.with_user(self.nurse).state, "issued")

    def test_pharmacy_is_notified_and_sees_the_queue(self):
        _appointment, encounter = self.visit()
        rx = self.prescribe(encounter)
        rx.with_user(self.doctor).action_issue()
        inbox = self.env["careos.notification"].with_user(self.pharmacist).careos_inbox()
        self.assertTrue(any("Prescription to dispense" in n["title"] for n in inbox["items"]))
        queue = self.env["careos.prescription"].with_user(self.pharmacist).careos_list(state="issued")
        self.assertEqual([r["id"] for r in queue], rx.ids)
        # The payload is readable by pharmacists (visit date via sudo).
        self.assertTrue(queue[0]["encounter"]["date"])

    def test_current_medications_on_patient_360(self):
        _appointment, encounter = self.visit()
        rx = self.prescribe(encounter)
        rx.with_user(self.doctor).action_issue()
        profile = self.patient.with_user(self.doctor).careos_get_profile()
        self.assertEqual([m["med"] for m in profile["current_medications"]], ["Lisinopril 10mg (30 tabs)"])
        self.assertIn("Prescription issued", [e["title"] for e in profile["timeline"]])
        self.assertFalse(self.patient.with_user(self.reception).careos_get_profile()["medications_access"])
