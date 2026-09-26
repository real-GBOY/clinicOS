from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.careos_base.models.authorization import has_role, require_role

PAYMENT_METHODS = [("cash", "Cash"), ("card", "Card"), ("bank", "Bank transfer")]
# Roles per billing action (spec §9 Finance row: reception collects payment,
# finance full, manager reads).
VIEW_ROLES = {"reception", "finance", "manager", "admin"}
BILL_ROLES = {"reception", "finance"}
REFUND_ROLES = {"finance"}


class CareosAppointmentType(models.Model):
    _inherit = "careos.appointment.type"

    product_id = fields.Many2one("product.product", string="Billing service", readonly=True, ondelete="restrict")
    price = fields.Float(related="product_id.list_price", readonly=False)

    @api.model_create_multi
    def create(self, vals_list):
        prices = [vals.pop("price", 0.0) for vals in vals_list]
        types = super().create(vals_list)
        for visit_type, price in zip(types, prices):
            visit_type._careos_ensure_product(price)
        return types

    def _careos_ensure_product(self, price=0.0):
        for visit_type in self.filtered(lambda t: not t.product_id):
            # Clinic services are tax-exempt by default; configure taxes on the product if needed.
            visit_type.product_id = self.env["product.product"].sudo().create({
                "name": _("Consultation — %s", visit_type.name), "type": "service", "list_price": price,
                "taxes_id": [(5, 0, 0)],
            })

    @api.model
    def _careos_init_products(self, prices=None):
        """Give existing visit types a billing product (module install)."""
        prices = prices or {}
        for visit_type in self.search([("product_id", "=", False)]):
            visit_type._careos_ensure_product(prices.get(visit_type.name, 0.0))


class CareosPatient(models.Model):
    _inherit = "careos.patient"

    def careos_get_profile(self):
        profile = super().careos_get_profile()
        profile["billing_access"] = has_role(self.env, VIEW_ROLES)
        if profile["billing_access"]:
            moves = self.env["careos.billing"]._careos_patient_moves(self)
            profile["balance_due"] = sum(moves.mapped("amount_residual"))
            profile["currency"] = self.company_id.currency_id.symbol
        return profile


class AccountMove(models.Model):
    _inherit = "account.move"

    careos_patient_id = fields.Many2one("careos.patient", index=True, readonly=True)
    careos_branch_id = fields.Many2one("careos.branch", index=True, readonly=True)
    careos_appointment_id = fields.Many2one("careos.appointment", index=True, readonly=True, string="Visit")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    careos_appointment_id = fields.Many2one("careos.appointment", index=True, readonly=True)
    careos_lab_order_id = fields.Many2one("careos.lab.order", index=True, readonly=True)
    careos_prescription_line_id = fields.Many2one("careos.prescription.line", index=True, readonly=True)


class CareosBilling(models.AbstractModel):
    """Healthcare billing on native Odoo Accounting.

    Invoices are real ``account.move`` records and payments real
    ``account.payment`` records; this service decides *what* is billable for a
    visit and enforces who may bill, collect or refund. Accounting objects are
    handled with sudo after these explicit role and branch checks, so front-desk
    staff never need accounting rights (spec §14.2: no custom invoice model).
    """

    _name = "careos.billing"
    _description = "CareOS Billing Service"

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @api.model
    def _careos_require(self, allowed):
        require_role(self.env, allowed, _("Your role does not allow this billing action."))

    @api.model
    def _careos_move(self, move_id):
        """Load an invoice the user may see: CareOS invoice at one of the
        user's branches."""
        self._careos_require(VIEW_ROLES)
        move = self.env["account.move"].sudo().browse(move_id).exists()
        if not move or not move.careos_patient_id:
            raise AccessError(_("Invoice not found."))
        if not self.env.su and move.careos_branch_id not in self.env.user.careos_branch_ids:
            raise AccessError(_("This invoice belongs to another branch."))
        return move

    @api.model
    def _careos_patient_moves(self, patient):
        moves = self.env["account.move"].sudo().search([
            ("careos_patient_id", "=", patient.id), ("move_type", "=", "out_invoice"), ("state", "!=", "cancel"),
        ], order="invoice_date desc, id desc")
        if not self.env.su:
            moves = moves.filtered(lambda m: m.careos_branch_id in self.env.user.careos_branch_ids)
        return moves

    # ------------------------------------------------------------------
    # What can be billed for a visit
    # ------------------------------------------------------------------

    @api.model
    def _careos_billable_lines(self, appointment):
        """Invoice line values for everything delivered in the visit and not
        billed yet: the consultation, lab tests, dispensed medicines."""
        appointment = appointment.sudo()
        Line = self.env["account.move.line"].sudo()
        billed = Line.search([("parent_state", "!=", "cancel"), "|", "|",
                              ("careos_appointment_id", "=", appointment.id),
                              ("careos_lab_order_id", "in", appointment.encounter_ids.lab_order_ids.ids),
                              ("careos_prescription_line_id", "in", appointment.encounter_ids.prescription_ids.line_ids.ids)])
        lines = []
        if appointment.state == "done" and appointment not in billed.careos_appointment_id:
            product = appointment.type_id.product_id
            if not product:
                appointment.type_id._careos_ensure_product()
                product = appointment.type_id.product_id
            lines.append({"product_id": product.id, "name": _("Consultation — %s", appointment.type_id.name),
                          "quantity": 1, "price_unit": product.list_price, "careos_appointment_id": appointment.id})
        for order in appointment.encounter_ids.lab_order_ids:
            if order not in billed.careos_lab_order_id:
                for test in order.test_ids:
                    lines.append({"product_id": test.product_id.id, "name": _("%s (Lab)", test.name), "quantity": 1,
                                  "price_unit": test.product_id.list_price, "careos_lab_order_id": order.id})
        for rx_line in appointment.encounter_ids.prescription_ids.filtered(
                lambda rx: rx.state in ("dispensed", "completed")).line_ids:
            if rx_line not in billed.careos_prescription_line_id:
                lines.append({"product_id": rx_line.product_id.id, "name": rx_line.product_id.name,
                              "quantity": rx_line.quantity, "price_unit": rx_line.product_id.list_price,
                              "careos_prescription_line_id": rx_line.id})
        return lines

    @api.model
    def careos_visit_billing(self, appointment_id):
        """Billing card on the appointment: its invoices and what is left to bill."""
        self._careos_require(VIEW_ROLES)
        appointment = self.env["careos.appointment"].browse(appointment_id)
        appointment.check_access("read")
        moves = self.env["account.move"].sudo().search([("careos_appointment_id", "=", appointment.id),
                                                        ("move_type", "=", "out_invoice")])
        pending = self._careos_billable_lines(appointment)
        return {
            "invoices": [self._careos_summary(m) for m in moves],
            "pending": [{"name": line["name"], "quantity": line["quantity"], "amount": line["quantity"] * line["price_unit"]}
                        for line in pending],
            "pending_total": sum(line["quantity"] * line["price_unit"] for line in pending),
            "currency": appointment.company_id.currency_id.symbol,
            "can_bill": bool(pending) and has_role(self.env, BILL_ROLES),
        }

    @api.model
    def careos_create_invoice(self, appointment_id):
        """Create (draft) the invoice for everything billable on the visit."""
        self._careos_require(BILL_ROLES)
        appointment = self.env["careos.appointment"].browse(appointment_id)
        appointment.check_access("read")
        lines = self._careos_billable_lines(appointment)
        if not lines:
            raise UserError(_("Nothing left to bill for this visit."))
        patient = appointment.patient_id
        move = self.env["account.move"].sudo().create({
            "move_type": "out_invoice",
            "partner_id": patient._careos_partner().id,
            "company_id": appointment.company_id.id,
            "invoice_date": fields.Date.context_today(self),
            "careos_patient_id": patient.id,
            "careos_branch_id": appointment.branch_id.id,
            "careos_appointment_id": appointment.id,
            "invoice_line_ids": [(0, 0, line) for line in lines],
        })
        return move.id

    # ------------------------------------------------------------------
    # Invoice lifecycle: Draft → Posted → Partially Paid → Paid · Posted → Refunded
    # ------------------------------------------------------------------

    @api.model
    def careos_post(self, move_id):
        self._careos_require(BILL_ROLES)
        move = self._careos_move(move_id)
        if move.state != "draft":
            raise UserError(_("Only draft invoices can be issued."))
        move.action_post()
        return self.careos_invoice_detail(move_id)

    @api.model
    def careos_register_payment(self, move_id, amount, method="cash"):
        self._careos_require(BILL_ROLES)
        move = self._careos_move(move_id)
        if move.state != "posted":
            raise UserError(_("Issue the invoice before recording a payment."))
        if not amount or amount <= 0:
            raise ValidationError(_("Enter an amount greater than zero."))
        if move.currency_id.compare_amounts(amount, move.amount_residual) > 0:
            raise ValidationError(_("The payment is larger than the balance due (%s).", move.amount_residual))
        journal = self._careos_payment_journal(move.company_id, method)
        wizard = self.env["account.payment.register"].sudo().with_context(
            active_model="account.move", active_ids=move.ids,
        ).create({"amount": amount, "journal_id": journal.id, "payment_date": fields.Date.context_today(self),
                  "communication": f"{move.name} · {dict(PAYMENT_METHODS).get(method, method)}"})
        wizard.action_create_payments()
        self._careos_notify_paid(move)
        return self.careos_invoice_detail(move_id)

    @api.model
    def careos_refund(self, move_id, reason):
        """Full credit note (finance only)."""
        self._careos_require(REFUND_ROLES)
        move = self._careos_move(move_id)
        if move.state != "posted" or move.payment_state == "reversed":
            raise UserError(_("Only issued invoices can be refunded."))
        if not (reason or "").strip():
            raise ValidationError(_("Give a reason for the refund."))
        credit = move._reverse_moves([{"ref": _("Refund: %s", reason), "invoice_date": fields.Date.context_today(self),
                                       "careos_patient_id": move.careos_patient_id.id,
                                       "careos_branch_id": move.careos_branch_id.id}], cancel=True)
        return {"credit_note": credit.name, **self.careos_invoice_detail(move_id)}

    @api.model
    def _careos_payment_journal(self, company, method):
        """Cash payments go to a cash journal when the chart of accounts has
        one; everything else (and cash without one) to the bank journal."""
        Journal = self.env["account.journal"].sudo()
        preferred = ("cash", "bank") if method == "cash" else ("bank",)
        for journal_type in preferred:
            journal = Journal.search([("company_id", "=", company.id), ("type", "=", journal_type)], limit=1)
            if journal:
                return journal
        raise UserError(_("No payment journal is configured."))

    def _careos_notify_paid(self, move):
        """Nothing to notify on payment today; hook for the portal/receipts."""

    # ------------------------------------------------------------------
    # Payloads
    # ------------------------------------------------------------------

    @api.model
    def _careos_status(self, move):
        today = fields.Date.context_today(self)
        if move.state == "draft":
            return "draft", _("Draft"), "neutral"
        if move.state == "cancel":
            return "cancelled", _("Cancelled"), "neutral"
        if move.payment_state == "reversed":
            return "refunded", _("Refunded"), "neutral"
        if move.payment_state in ("paid", "in_payment"):
            return "paid", _("Paid"), "success"
        if move.payment_state == "partial":
            return "partial", _("Partially paid"), "warning"
        if move.invoice_date_due and move.invoice_date_due < today:
            return "overdue", _("Overdue"), "danger"
        return "pending", _("Pending"), "neutral"

    @api.model
    def _careos_summary(self, move):
        key, label, tone = self._careos_status(move)
        return {
            "id": move.id,
            "name": move.name if move.name and move.name != "/" else _("Draft invoice"),
            "date": fields.Date.to_string(move.invoice_date) if move.invoice_date else False,
            "due": fields.Date.to_string(move.invoice_date_due) if move.invoice_date_due else False,
            "patient": {"id": move.careos_patient_id.id, "name": move.careos_patient_id.name},
            "total": move.amount_total,
            "paid": move.amount_total - move.amount_residual if move.state == "posted" else 0.0,
            "balance": move.amount_residual if move.state == "posted" else move.amount_total,
            "currency": move.currency_id.symbol,
            "status": key,
            "status_label": label,
            "tone": tone,
        }

    @api.model
    def careos_invoice_detail(self, move_id):
        move = self._careos_move(move_id)
        can_bill = has_role(self.env, BILL_ROLES)
        summary = self._careos_summary(move)
        payments = [{
            "date": fields.Date.to_string(payment.date),
            # Method recorded in the memo ("INV/… · Card"); journal name otherwise.
            "method": payment.memo.split(" · ")[-1] if payment.memo and " · " in payment.memo else payment.journal_id.name,
            "amount": payment.amount,
        } for payment in (move._get_reconciled_payments() if move.state == "posted" else [])]
        return {
            **summary,
            "appointment_id": move.careos_appointment_id.id or False,
            "branch": move.careos_branch_id.name,
            "lines": [{
                "id": line.id, "service": line.name, "qty": line.quantity, "unit": line.price_unit, "total": line.price_total,
            } for line in move.invoice_line_ids],
            "payments": payments,
            "can_post": can_bill and move.state == "draft",
            "can_pay": can_bill and move.state == "posted" and move.payment_state in ("not_paid", "partial"),
            "can_refund": has_role(self.env, REFUND_ROLES) and move.state == "posted"
            and move.payment_state != "reversed",
            "methods": PAYMENT_METHODS,
        }

    @api.model
    def careos_invoice_list(self, status=None, query=None, limit=100):
        self._careos_require(VIEW_ROLES)
        domain = [("careos_patient_id", "!=", False), ("move_type", "=", "out_invoice"), ("state", "!=", "cancel")]
        branch = self.env.user.careos_branch_id
        if branch:
            domain.append(("careos_branch_id", "=", branch.id))
        elif not self.env.su:
            domain.append(("careos_branch_id", "in", self.env.user.careos_branch_ids.ids))
        if (query or "").strip():
            domain += ["|", ("name", "ilike", query.strip()), ("careos_patient_id.name", "ilike", query.strip())]
        moves = self.env["account.move"].sudo().search(domain, order="invoice_date desc, id desc", limit=limit)
        rows = [self._careos_summary(m) for m in moves]
        if status:
            rows = [r for r in rows if r["status"] == status or (status == "unpaid" and r["status"] in ("pending", "partial", "overdue"))]
        return rows

    @api.model
    def careos_patient_invoices(self, patient_id):
        self._careos_require(VIEW_ROLES)
        patient = self.env["careos.patient"].browse(patient_id)
        patient.check_access("read")
        return [self._careos_summary(m) for m in self._careos_patient_moves(patient)]

    @api.model
    def _careos_cron_overdue(self):
        """Daily: tell the front desk and finance about overdue invoices."""
        Notification = self.env["careos.notification"]
        today = fields.Date.context_today(self)
        overdue = self.env["account.move"].search([
            ("careos_patient_id", "!=", False), ("state", "=", "posted"), ("move_type", "=", "out_invoice"),
            ("payment_state", "in", ("not_paid", "partial")), ("invoice_date_due", "<", today),
        ])
        for move in overdue:
            users = Notification._careos_users_with_roles(["reception", "finance"], move.careos_branch_id)
            Notification._careos_notify(users, _("Payment overdue — %s", move.name),
                                        body=f"{move.careos_patient_id.name} · {move.amount_residual:,.0f} {move.currency_id.symbol}",
                                        kind="danger", screen="invoice", res_id=move.id, dedupe_key=f"overdue-{move.id}")
