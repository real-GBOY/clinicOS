from datetime import timedelta

from odoo import api, fields, models

# Items from the CareOS prototype inventory screen, plus the medicines used in
# demo prescriptions. (name, strength, type, stock, reorder, expiry in days, price)
DEMO_ITEMS = [
    ("Lisinopril 10mg (30 tabs)", "10mg", "medication", 1240, 300, 640, 250),
    ("Atorvastatin 20mg (30 tabs)", "20mg", "medication", 85, 150, 540, 150),
    ("Amoxicillin 500mg (21 caps)", "500mg", "medication", 410, 200, 21, 95),
    ("Aspirin 75mg (30 tabs)", "75mg", "medication", 900, 200, 420, 40),
    ("Amlodipine 5mg (30 tabs)", "5mg", "medication", 620, 150, 480, 120),
    ("Metformin 500mg (60 tabs)", "500mg", "medication", 530, 150, 400, 85),
    ("Surgical gloves (M, box of 100)", "", "supply", 2300, 500, None, 180),
    ("Syringes 5ml", "", "supply", 60, 200, None, 4),
    ("ECG electrodes", "", "supply", 150, 100, 25, 12),
]


class CareosInventory(models.AbstractModel):
    _inherit = "careos.inventory"

    @api.model
    def _careos_demo_inventory(self):
        env = self.env
        cairo = env.ref("careos_base.branch_cairo")
        cairo.warehouse_id = env.ref("stock.warehouse0")
        for xmlid, name, code in (("branch_alexandria", "Alexandria Branch", "ALX"), ("branch_menoufia", "Menoufia Branch", "MNF")):
            branch = env.ref(f"careos_base.{xmlid}")
            if not branch.warehouse_id:
                branch.warehouse_id = env["stock.warehouse"].create({"name": name, "code": code})
        fefo = env.ref("product_expiry.removal_fefo", raise_if_not_found=False)
        category = env["product.category"].create({"name": "Pharmacy", "removal_strategy_id": fefo and fefo.id})
        today = fields.Date.context_today(self)
        warehouse = cairo.warehouse_id
        for index, (name, strength, item_type, stock, reorder, expiry_days, price) in enumerate(DEMO_ITEMS):
            tracked = expiry_days is not None
            product = env["product.product"].create({
                "name": name,
                "type": "consu",
                "is_storable": True,
                "careos_item_type": item_type,
                "careos_strength": strength,
                "list_price": price,
                "categ_id": category.id,
                "tracking": "lot" if tracked else "none",
                "use_expiration_date": tracked,
            })
            env["ir.model.data"].create({
                "name": f"demo_item_{index}", "module": "careos_demo", "model": "product.product", "res_id": product.id,
                "noupdate": True,  # created from code: keep out of the module cleanup
            })
            env["stock.warehouse.orderpoint"].create({
                "warehouse_id": warehouse.id, "location_id": warehouse.lot_stock_id.id,
                "product_id": product.id, "product_min_qty": reorder, "product_max_qty": reorder * 3,
            })
            lot_name = f"B{today.strftime('%y%m')}-{index + 1:03d}" if tracked else None
            expiry = fields.Datetime.to_string(today + timedelta(days=expiry_days)) if tracked else None
            self._careos_adjust_stock(warehouse, product, stock, lot_name, expiry)
