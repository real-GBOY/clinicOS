from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

STATES = [
    ("ordered", "Ordered"),
    ("collected", "Sample Collected"),
    ("processing", "Processing"),
    ("result_entered", "Result Entered"),
    ("verified", "Verified"),
    ("completed", "Completed"),
]
# Spec §6: Ordered → Sample Collected → Processing → Result Entered → Verified → Completed.
# Verified = technically validated by the lab; Completed = reviewed by the ordering doctor.
TRANSITIONS = {
    "collect": ({"ordered"}, "collected", {"lab", "nurse"}),
    "process": ({"collected"}, "processing", {"lab"}),
    "enter_results": ({"processing"}, "result_entered", {"lab"}),
    "verify": ({"result_entered"}, "verified", {"lab"}),
    "review": ({"verified"}, "completed", {"doctor"}),
}
TIMESTAMP = {"collected": "collected_at", "processing": "processing_at", "result_entered": "result_at",
             "verified": "verified_at", "completed": "completed_at"}
ACTOR = {"collected": "collected_by_id", "verified": "verified_by_id", "completed": "reviewed_by_id"}


class CareosLabTest(models.Model):
    """A test in the lab catalogue with its measured parameters. A plain code
    field; LOINC is a later integration (spec §14.3)."""

    _name = "careos.lab.test"
    _description = "Lab Test"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    sample_type = fields.Selection([("blood", "Blood"), ("urine", "Urine"), ("swab", "Swab"), ("other", "Other")],
                                   default="blood", required=True)
    parameter_ids = fields.One2many("careos.lab.test.parameter", "test_id", string="Parameters")
    product_id = fields.Many2one("product.product", string="Billing service", readonly=True, ondelete="restrict")
    price = fields.Float(related="product_id.list_price", readonly=False)

    @api.model_create_multi
    def create(self, vals_list):
        # The price lives on the billing service product, created here.
        prices = [vals.pop("price", 0.0) for vals in vals_list]
        tests = super().create(vals_list)
        for test, price in zip(tests, prices):
            if not test.product_id:
                test.product_id = self.env["product.product"].sudo().create({
                    "name": f"{test.name} (Lab)", "type": "service", "list_price": price,
                })
                if "taxes_id" in test.product_id._fields:  # clinic services are tax-exempt by default
                    test.product_id.taxes_id = [(5, 0, 0)]
        return tests


class CareosLabTestParameter(models.Model):
    _name = "careos.lab.test.parameter"
    _description = "Lab Test Parameter"
    _order = "test_id, sequence, id"

    test_id = fields.Many2one("careos.lab.test", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    unit = fields.Char()
    ref_low = fields.Float(string="Reference low")
    ref_high = fields.Float(string="Reference high")

    def _range_label(self):
        self.ensure_one()
        if self.ref_low or self.ref_high:
            return f"{self.ref_low:g}–{self.ref_high:g}"
        return ""


class CareosLabOrder(models.Model):
    _name = "careos.lab.order"
    _description = "Lab Order"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"
    _rec_names_search = ["name", "patient_id.name", "patient_id.ref"]

    name = fields.Char(required=True, readonly=True, copy=False, index=True, default=lambda self: _("New"))
    encounter_id = fields.Many2one("careos.encounter", required=True, readonly=True, index=True, ondelete="restrict")
    patient_id = fields.Many2one(related="encounter_id.patient_id", store=True, index=True)
    provider_id = fields.Many2one(related="encounter_id.provider_id", store=True, index=True, string="Ordered by")
    branch_id = fields.Many2one(related="encounter_id.branch_id", store=True, index=True)
    company_id = fields.Many2one(related="encounter_id.company_id", store=True, index=True)
    state = fields.Selection(STATES, required=True, default="ordered", index=True, tracking=True)
    priority = fields.Selection([("routine", "Routine"), ("urgent", "Urgent")], default="routine", required=True)
    test_ids = fields.Many2many("careos.lab.test", string="Tests", required=True)
    result_ids = fields.One2many("careos.lab.result", "order_id", string="Results")
    clinical_note = fields.Char(help="Context for the lab, e.g. fasting sample.")

    collected_at = fields.Datetime(readonly=True)
    collected_by_id = fields.Many2one("res.users", readonly=True)
    processing_at = fields.Datetime(readonly=True)
    result_at = fields.Datetime(readonly=True)
    verified_at = fields.Datetime(readonly=True)
    verified_by_id = fields.Many2one("res.users", readonly=True)
    completed_at = fields.Datetime(readonly=True)
    reviewed_by_id = fields.Many2one("res.users", readonly=True)
    has_abnormal = fields.Boolean(compute="_compute_has_abnormal", store=True)

    @api.depends("result_ids.flag")
    def _compute_has_abnormal(self):
        for order in self:
            order.has_abnormal = any(flag in ("low", "high") for flag in order.result_ids.mapped("flag"))

    def _compute_display_name(self):
        for order in self:
            order.display_name = f"{order.name} · {order.patient_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and "doctor" not in self.env.user._careos_role_keys():
            raise AccessError(_("Only doctors can order laboratory tests."))
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("careos.lab.order") or _("New")
        orders = super().create(vals_list)
        for order in orders:
            # System imports (sudo) may attach historic orders to closed encounters.
            if not self.env.su and order.encounter_id.state != "open":
                raise UserError(_("Lab tests can only be ordered during an open encounter."))
            if not order.test_ids:
                raise ValidationError(_("Choose at least one test."))
            order.sudo()._careos_prepare_results()
        return orders

    def write(self, vals):
        if "state" in vals and not self.env.context.get("careos_lab_internal"):
            raise UserError(_("Lab order status changes only through its workflow."))
        return super().write(vals)

    def _careos_prepare_results(self):
        """One result row per parameter of every ordered test."""
        Result = self.env["careos.lab.result"]
        for order in self:
            for test in order.test_ids:
                for parameter in test.parameter_ids:
                    Result.create({"order_id": order.id, "test_id": test.id, "parameter_id": parameter.id})

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _careos_transition(self, action):
        sources, target, roles = TRANSITIONS[action]
        if not self.env.su and not roles & set(self.env.user._careos_role_keys()):
            raise AccessError(_("Your role cannot perform this laboratory step."))
        self.check_access("write")
        for order in self:
            if order.state not in sources:
                raise UserError(_("%(ref)s is %(state)s.", ref=order.name, state=dict(STATES)[order.state]))
        vals = {"state": target, TIMESTAMP[target]: fields.Datetime.now()}
        if target in ACTOR:
            vals[ACTOR[target]] = self.env.uid
        self.with_context(careos_lab_internal=True).write(vals)
        return True

    def action_collect(self):
        return self._careos_transition("collect")

    def action_process(self):
        return self._careos_transition("process")

    def action_verify(self):
        return self._careos_transition("verify")

    def action_review(self):
        return self._careos_transition("review")

    def careos_save_results(self, values):
        """Store result values ({result_id: value}) while processing."""
        self.ensure_one()
        if not self.env.su and "lab" not in self.env.user._careos_role_keys():
            raise AccessError(_("Only the laboratory enters results."))
        if self.state != "processing":
            raise UserError(_("Results can be entered while the sample is processing."))
        self.check_access("write")
        for result in self.result_ids:
            key = str(result.id)
            if key in values:
                raw = values[key]
                result.value = float(raw) if raw not in ("", None, False) else False
                result.has_value = raw not in ("", None, False)
        return self.careos_get_detail()

    def action_submit_results(self, values=None):
        """Save and release results to the ordering doctor."""
        self.ensure_one()
        if values:
            self.careos_save_results(values)
        missing = self.result_ids.filtered(lambda r: not r.has_value)
        if missing:
            raise UserError(_("Enter a value for every parameter (%s missing).", ", ".join(missing.mapped("parameter_id.name"))))
        self._careos_transition("enter_results")
        doctor = self.provider_id.user_id
        if doctor:
            tests = ", ".join(self.test_ids.mapped("name"))
            self.env["careos.notification"]._careos_notify(
                doctor, _("Lab result ready — %(patient)s (%(tests)s)", patient=self.patient_id.name, tests=tests),
                body=_("Abnormal values flagged") if self.has_abnormal else "", kind="danger" if self.has_abnormal else "info",
                screen="lab", res_id=self.id,
            )
        return self.careos_get_detail()

    # ------------------------------------------------------------------
    # Payloads
    # ------------------------------------------------------------------

    def _careos_actions(self):
        roles = set(self.env.user._careos_role_keys())
        can_write = self.has_access("write")
        actions = []
        for action, (sources, _target, action_roles) in TRANSITIONS.items():
            if self.state in sources and can_write and (self.env.su or action_roles & roles):
                actions.append(action)
        return actions

    def _careos_payload(self, with_results=False):
        self.ensure_one()
        to_str = fields.Datetime.to_string
        payload = {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": dict(STATES)[self.state],
            "priority": self.priority,
            "patient": {"id": self.patient_id.id, "name": self.patient_id.name, "ref": self.patient_id.ref},
            "provider": {"id": self.provider_id.id, "name": self.provider_id.name},
            "tests": ", ".join(self.test_ids.mapped("name")),
            "ordered_at": to_str(self.create_date),
            "has_abnormal": self.has_abnormal,
            "encounter_id": self.encounter_id.id,
            "actions": self._careos_actions(),
        }
        if with_results:
            payload["results"] = [r._careos_payload() for r in self.result_ids]
            payload["can_enter_results"] = "enter_results" in payload["actions"]
            payload["clinical_note"] = self.clinical_note or ""
            payload["verified_by"] = self.verified_by_id.name or ""
            payload["reviewed_by"] = self.reviewed_by_id.name or ""
        return payload

    def careos_get_detail(self):
        self.ensure_one()
        self.check_access("read")
        return self._careos_payload(with_results=True)

    @api.model
    def careos_worklist(self, scope="active", limit=100):
        domain = []
        if scope == "active":
            domain.append(("state", "not in", ("completed",)))
        elif scope == "completed":
            domain.append(("state", "=", "completed"))
        branch = self.env.user.careos_branch_id
        if branch:
            domain.append(("branch_id", "=", branch.id))
        return [o._careos_payload() for o in self.search(domain, limit=limit)]

    @api.model
    def careos_catalogue(self):
        return [{"id": t.id, "name": t.name, "code": t.code or ""} for t in self.env["careos.lab.test"].search([])]

    def _careos_search_result(self):
        self.ensure_one()
        return {"id": self.id, "title": self.name,
                "detail": f"{', '.join(self.test_ids.mapped('name'))} · {dict(STATES)[self.state]}"}


class CareosLabResult(models.Model):
    _name = "careos.lab.result"
    _description = "Lab Result"
    _order = "order_id, test_id, parameter_id"

    order_id = fields.Many2one("careos.lab.order", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", store=True, index=True)
    patient_id = fields.Many2one(related="order_id.patient_id", store=True, index=True)
    test_id = fields.Many2one("careos.lab.test", required=True)
    parameter_id = fields.Many2one("careos.lab.test.parameter", required=True)
    value = fields.Float(digits=(10, 2))
    has_value = fields.Boolean()
    unit = fields.Char(related="parameter_id.unit")
    flag = fields.Selection([("normal", "Normal"), ("low", "Low"), ("high", "High")], compute="_compute_flag", store=True)

    @api.depends("value", "has_value", "parameter_id.ref_low", "parameter_id.ref_high")
    def _compute_flag(self):
        for result in self:
            param = result.parameter_id
            if not result.has_value or not (param.ref_low or param.ref_high):
                result.flag = False
            elif param.ref_low and result.value < param.ref_low:
                result.flag = "low"
            elif param.ref_high and result.value > param.ref_high:
                result.flag = "high"
            else:
                result.flag = "normal"

    def write(self, vals):
        if not self.env.su and set(vals) & {"value", "has_value"}:
            if self.order_id.filtered(lambda o: o.state != "processing"):
                raise UserError(_("Results are locked once released."))
        return super().write(vals)

    def _careos_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "test": self.test_id.name,
            "name": self.parameter_id.name,
            "value": self.value if self.has_value else "",
            "unit": self.unit or "",
            "range": self.parameter_id._range_label(),
            "flag": self.flag or "",
        }
