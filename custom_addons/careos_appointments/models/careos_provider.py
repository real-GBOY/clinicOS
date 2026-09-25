from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CareosProvider(models.Model):
    """A clinician who can be booked. Linked to a user when the provider logs
    in to CareOS (so they see their own schedule); visiting consultants may
    have no login. Linking to hr.employee is deferred to the HR module."""

    _name = "careos.provider"
    _description = "Care Provider"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    user_id = fields.Many2one("res.users", string="CareOS login", index=True, ondelete="set null")
    specialty = fields.Char()
    department_id = fields.Many2one("careos.department")
    branch_ids = fields.Many2many(
        "careos.branch", "careos_provider_branch_rel", "provider_id", "branch_id",
        string="Practices at", required=True,
    )
    default_room_id = fields.Many2one("careos.room", domain="[('branch_id', 'in', branch_ids)]")
    company_id = fields.Many2one("res.company", required=True, index=True, default=lambda self: self.env.company)

    _user_uniq = models.Constraint("UNIQUE(user_id)", "A user can be linked to only one provider.")

    @api.constrains("default_room_id", "branch_ids")
    def _check_default_room(self):
        for provider in self:
            if provider.default_room_id and provider.default_room_id.branch_id not in provider.branch_ids:
                raise ValidationError(_("The default room must be at one of the provider's branches."))

    def _careos_ref(self):
        return {"id": self.id, "name": self.name} if self else False
