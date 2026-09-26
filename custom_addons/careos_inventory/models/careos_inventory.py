from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.addons.careos_base.models.authorization import has_role, require_role

ITEM_TYPES = [("medication", "Medication"), ("supply", "Supplies"), ("lab", "Lab consumable")]
EXPIRY_WARNING_DAYS = 30
VIEW_ROLES = {"pharmacy", "lab", "finance", "manager", "admin"}
RECEIVE_ROLES = {"pharmacy", "admin"}


class ProductTemplate(models.Model):
    _inherit = "product.template"

    careos_item_type = fields.Selection(ITEM_TYPES, string="CareOS item type", index=True,
                                        help="Set to make the product appear in CareOS inventory.")
    careos_strength = fields.Char(string="Strength", help="e.g. 10mg — shown on prescriptions.")


class CareosBranch(models.Model):
    _inherit = "careos.branch"

    warehouse_id = fields.Many2one("stock.warehouse", help="Stock location for this branch's pharmacy and supplies.")


class CareosInventory(models.AbstractModel):
    """Inventory service for CareOS screens. Stock itself is native Odoo
    Inventory (quants, lots with expiry, reordering rules, pickings); this
    layer reads it per branch and exposes the few actions clinics need.
    Reads use sudo after an explicit CareOS role check so read-only roles
    (finance, manager) do not need Inventory application rights."""

    _name = "careos.inventory"
    _description = "CareOS Inventory Service"

    @api.model
    def _careos_check_roles(self, allowed):
        require_role(self.env, allowed, _("Your role does not have access to inventory."))

    @api.model
    def _careos_warehouse(self, branch=None):
        branch = branch or self.env.user.careos_branch_id
        if not branch:
            raise UserError(_("Select a branch first."))
        if not branch.sudo().warehouse_id:
            raise UserError(_("%s has no stock location configured.", branch.name))
        return branch.sudo().warehouse_id

    @api.model
    def _careos_item_rows(self, warehouse, products):
        today = fields.Date.context_today(self)
        warn_date = today + timedelta(days=EXPIRY_WARNING_DAYS)
        Quant = self.env["stock.quant"].sudo()
        quants = Quant.search([
            ("product_id", "in", products.ids),
            ("location_id", "child_of", warehouse.lot_stock_id.id),
            ("quantity", ">", 0),
        ])
        orderpoints = self.env["stock.warehouse.orderpoint"].sudo().search([
            ("warehouse_id", "=", warehouse.id), ("product_id", "in", products.ids),
        ])
        reorder_by_product = {op.product_id.id: op.product_min_qty for op in orderpoints}
        rows = []
        for product in products:
            product_quants = quants.filtered(lambda q: q.product_id == product)
            stock = sum(product_quants.mapped("quantity"))
            expiries = [q.lot_id.expiration_date.date() for q in product_quants if q.lot_id.expiration_date]
            nearest = min(expiries) if expiries else False
            reorder = reorder_by_product.get(product.id, 0)
            if nearest and nearest <= warn_date:
                status, tone = "expiring", "danger"
            elif reorder and stock < reorder:
                status, tone = "low", "warning"
            else:
                status, tone = "ok", "success"
            rows.append({
                "id": product.id,
                "name": product.display_name,
                "item_type": product.careos_item_type,
                "category": dict(ITEM_TYPES).get(product.careos_item_type, ""),
                "stock": stock,
                "uom": product.uom_id.name,
                "reorder": reorder,
                "expiry": nearest and fields.Date.to_string(nearest),
                "status": status,
                "status_label": {"expiring": _("Expiring soon"), "low": _("Low stock"), "ok": _("OK")}[status],
                "tone": tone,
                "price": product.list_price,
            })
        return rows

    @api.model
    def careos_overview(self, query=None, item_type=None):
        """Prototype "Inventory": KPIs and item table for the current branch."""
        self._careos_check_roles(VIEW_ROLES)
        warehouse = self._careos_warehouse()
        domain = [("careos_item_type", "!=", False)]
        if item_type:
            domain.append(("careos_item_type", "=", item_type))
        if (query or "").strip():
            domain.append(("name", "ilike", query.strip()))
        products = self.env["product.product"].sudo().search(domain, order="name")
        rows = self._careos_item_rows(warehouse, products)
        all_rows = rows if not (query or item_type) else self._careos_item_rows(
            warehouse, self.env["product.product"].sudo().search([("careos_item_type", "!=", False)]))
        return {
            "branch": self.env.user.careos_branch_id.name,
            "kpis": [
                {"key": "skus", "label": _("Total SKUs"), "value": len(all_rows), "tone": ""},
                {"key": "low", "label": _("Low stock"), "value": sum(r["status"] == "low" for r in all_rows), "tone": "warning"},
                {"key": "expiring", "label": _("Expiring < %s days", EXPIRY_WARNING_DAYS),
                 "value": sum(r["status"] == "expiring" for r in all_rows), "tone": "danger"},
            ],
            "items": rows,
            "can_receive": has_role(self.env, RECEIVE_ROLES),
        }

    @api.model
    def careos_receive(self, product_id, quantity, lot_name=None, expiration_date=None):
        """Receive stock into the branch store (goods-in / inventory count)."""
        self._careos_check_roles(RECEIVE_ROLES)
        if not quantity or quantity <= 0:
            raise ValidationError(_("Enter a quantity greater than zero."))
        warehouse = self._careos_warehouse()
        product = self.env["product.product"].sudo().browse(product_id)
        if not product.exists() or not product.careos_item_type:
            raise ValidationError(_("Unknown inventory item."))
        lot = self.env["stock.lot"]
        if product.tracking != "none":
            if not lot_name:
                raise ValidationError(_("%s is batch-tracked: enter the batch number.", product.name))
            lot = lot.sudo().search([("name", "=", lot_name), ("product_id", "=", product.id)], limit=1) or lot.sudo().create({
                "name": lot_name, "product_id": product.id, "company_id": warehouse.company_id.id,
                "expiration_date": expiration_date and fields.Datetime.to_datetime(expiration_date),
            })
        quant = self.env["stock.quant"].sudo().with_context(inventory_mode=True).search([
            ("product_id", "=", product.id), ("location_id", "=", warehouse.lot_stock_id.id), ("lot_id", "=", lot.id),
        ], limit=1)
        if quant:
            quant.inventory_quantity = quant.quantity + quantity
        else:
            quant = self.env["stock.quant"].sudo().with_context(inventory_mode=True).create({
                "product_id": product.id, "location_id": warehouse.lot_stock_id.id, "lot_id": lot.id,
                "inventory_quantity": quantity,
            })
        quant.action_apply_inventory()
        return self.careos_overview()

    @api.model
    def _careos_consume(self, branch, lines, origin):
        """Issue stock from the branch store to the patient (dispensing).
        ``lines``: list of (product, quantity). Validated immediately;
        raises if stock is insufficient. Returns the picking."""
        warehouse = self._careos_warehouse(branch)
        Picking = self.env["stock.picking"].sudo()
        picking_type = warehouse.out_type_id
        picking = Picking.create({
            "picking_type_id": picking_type.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "origin": origin,
            "move_ids": [(0, 0, {
                "product_id": product.id, "product_uom_qty": qty, "product_uom": product.uom_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            }) for product, qty in lines],
        })
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            if move.product_uom.compare(move.quantity, move.product_uom_qty) < 0:
                raise UserError(_("Not enough %(product)s in stock (%(available)s available).",
                                  product=move.product_id.display_name, available=move.quantity))
        picking.move_ids.picked = True
        picking.with_context(skip_backorder=True, skip_sms=True).button_validate()
        return picking

    @api.model
    def _careos_cron_low_stock(self):
        """Daily: notify pharmacy and managers about low or expiring stock."""
        Notification = self.env["careos.notification"]
        for branch in self.env["careos.branch"].search([("warehouse_id", "!=", False)]):
            products = self.env["product.product"].search([("careos_item_type", "!=", False)])
            for row in self.sudo()._careos_item_rows(branch.warehouse_id, products):
                if row["status"] == "ok":
                    continue
                title = (_("Low stock: %s", row["name"]) if row["status"] == "low"
                         else _("Expiring soon: %s", row["name"]))
                users = Notification._careos_users_with_roles(["pharmacy", "manager"], branch)
                Notification._careos_notify(
                    users, title, body=branch.name, kind="warning", screen="inventory",
                    dedupe_key=f"stock-{row['status']}-{branch.id}-{row['id']}",
                )
