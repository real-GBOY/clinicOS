from odoo import fields, models


class CareosDepartment(models.Model):
    """A clinical specialty unit inside a branch (Cardiology, Dermatology…)."""

    _name = "careos.department"
    _description = "Clinic Department"
    _order = "branch_id, sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    branch_id = fields.Many2one("careos.branch", required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one(related="branch_id.company_id", store=True, index=True)

    _name_branch_uniq = models.Constraint(
        "UNIQUE(name, branch_id)", "A department with this name already exists in the branch."
    )

    def _compute_display_name(self):
        for dept in self:
            dept.display_name = f"{dept.name} · {dept.branch_id.name}" if dept.branch_id else dept.name
