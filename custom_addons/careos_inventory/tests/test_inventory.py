from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "careos")
class TestInventory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.branch = cls.env["careos.branch"].create({"name": "Stock Branch", "code": "STK"})
        cls.warehouse = cls.env["stock.warehouse"].create({"name": "Stock Branch store", "code": "STK"})
        cls.branch.warehouse_id = cls.warehouse
        vals = {"careos_branch_ids": [(6, 0, cls.branch.ids)], "careos_branch_id": cls.branch.id}
        cls.pharmacist = new_test_user(cls.env, login="i_pharm", groups="careos_base.group_careos_pharmacist", **vals)
        cls.manager = new_test_user(cls.env, login="i_manager", groups="careos_base.group_careos_manager", **vals)
        cls.reception = new_test_user(cls.env, login="i_reception", groups="careos_base.group_careos_reception", **vals)
        Product = cls.env["product.product"]
        cls.tracked = Product.create({"name": "Atorvastatin 20mg", "type": "consu", "is_storable": True,
                                      "careos_item_type": "medication", "tracking": "lot", "use_expiration_date": True})
        cls.gloves = Product.create({"name": "Gloves", "type": "consu", "is_storable": True, "careos_item_type": "supply"})
        cls.env["stock.warehouse.orderpoint"].create({"warehouse_id": cls.warehouse.id, "location_id": cls.warehouse.lot_stock_id.id,
                                                      "product_id": cls.gloves.id, "product_min_qty": 100, "product_max_qty": 300})

    def rows(self, user):
        return {r["name"]: r for r in self.env["careos.inventory"].with_user(user).careos_overview()["items"]}

    def test_receive_and_status(self):
        Inventory = self.env["careos.inventory"].with_user(self.pharmacist)
        soon = (date.today() + timedelta(days=10)).isoformat()
        Inventory.careos_receive(self.tracked.id, 40, "B-001", soon)
        Inventory.careos_receive(self.gloves.id, 50)
        rows = self.rows(self.pharmacist)
        self.assertEqual((rows["Atorvastatin 20mg"]["stock"], rows["Atorvastatin 20mg"]["status"]), (40, "expiring"))
        self.assertEqual((rows["Gloves"]["stock"], rows["Gloves"]["status"]), (50, "low"))
        Inventory.careos_receive(self.gloves.id, 100)
        self.assertEqual(self.rows(self.pharmacist)["Gloves"]["status"], "ok")
        kpis = {k["key"]: k["value"] for k in Inventory.careos_overview()["kpis"]}
        # Demo databases carry more items: count every CareOS item, but only ours are low/expiring here.
        total = self.env["product.product"].search_count([("careos_item_type", "!=", False)])
        self.assertEqual(kpis["skus"], total)
        statuses = {name: row["status"] for name, row in self.rows(self.pharmacist).items()}
        self.assertEqual((statuses["Gloves"], statuses["Atorvastatin 20mg"]), ("ok", "expiring"))

    def test_receive_validation(self):
        Inventory = self.env["careos.inventory"].with_user(self.pharmacist)
        with self.assertRaises(ValidationError):
            Inventory.careos_receive(self.tracked.id, 10)  # batch number required
        with self.assertRaises(ValidationError):
            Inventory.careos_receive(self.gloves.id, 0)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_roles(self):
        self.assertTrue(self.rows(self.manager))  # managers read (spec: Inventory "Read")
        with self.assertRaises(AccessError):
            self.env["careos.inventory"].with_user(self.manager).careos_receive(self.gloves.id, 5)
        with self.assertRaises(AccessError):
            self.env["careos.inventory"].with_user(self.reception).careos_overview()

    def test_low_stock_alert_notifies_once(self):
        self.env["careos.inventory"].with_user(self.pharmacist).careos_receive(self.gloves.id, 5)
        Inventory = self.env["careos.inventory"]
        Inventory._careos_cron_low_stock()
        Inventory._careos_cron_low_stock()
        titles = [n["title"] for n in self.env["careos.notification"].with_user(self.pharmacist).careos_inbox()["items"]]
        self.assertEqual(titles.count("Low stock: Gloves"), 1)
