from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tz_get


class CareosBranch(models.Model):
    """A physical clinic location. Operational records (appointments, queue,
    encounters) are scoped to a branch; the legal/financial boundary stays the
    Odoo company, so a clinic group with shared finance needs one company and
    several branches."""

    _name = "careos.branch"
    _description = "Clinic Branch"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Short code used in references, e.g. CAI.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    timezone = fields.Selection(_tz_get, default=lambda self: self.env.user.tz or "UTC")
    phone = fields.Char()
    street = fields.Char()
    city = fields.Char()
    country_id = fields.Many2one("res.country")
    department_ids = fields.One2many("careos.department", "branch_id", string="Departments")

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A branch code must be unique within the organization."
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = vals["code"].strip().upper()
        return super().write(vals)
