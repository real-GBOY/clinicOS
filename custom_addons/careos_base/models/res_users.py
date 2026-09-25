from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

# CareOS role key -> security group xmlid. Keys are what the web client uses to
# decide which workspaces to show; the groups are what the server enforces.
CAREOS_ROLES = {
    "reception": "careos_base.group_careos_reception",
    "doctor": "careos_base.group_careos_doctor",
    "nurse": "careos_base.group_careos_nurse",
    "lab": "careos_base.group_careos_lab",
    "pharmacy": "careos_base.group_careos_pharmacist",
    "finance": "careos_base.group_careos_finance",
    "manager": "careos_base.group_careos_manager",
    "admin": "careos_base.group_careos_admin",
}


class ResUsers(models.Model):
    _inherit = "res.users"

    careos_branch_ids = fields.Many2many(
        "careos.branch",
        "careos_branch_users_rel",
        "user_id",
        "branch_id",
        string="Allowed Branches",
        help="Branches whose operational records this user works with.",
    )
    careos_branch_id = fields.Many2one(
        "careos.branch",
        string="Current Branch",
        help="Branch context used for defaults and operational views.",
    )
    careos_department_id = fields.Many2one(
        "careos.department",
        string="Department",
        help="Shown in the CareOS header and used as the default department.",
    )

    @api.constrains("careos_branch_id", "careos_branch_ids")
    def _check_careos_branch(self):
        for user in self:
            if user.careos_branch_id and user.careos_branch_id not in user.careos_branch_ids:
                raise ValidationError(_("The current branch must be one of the user's allowed branches."))

    def _careos_role_keys(self):
        self.ensure_one()
        return [key for key, xmlid in CAREOS_ROLES.items() if self.has_group(xmlid)]

    @api.model
    def careos_get_session_context(self):
        """Everything the CareOS shell needs to render for the current user."""
        user = self.env.user
        if not user.has_group("careos_base.group_careos_user"):
            raise AccessError(_("You do not have access to CareOS."))
        branches = user.careos_branch_ids.filtered("active")
        current = user.careos_branch_id if user.careos_branch_id in branches else branches[:1]
        return {
            "user_id": user.id,
            "name": user.name,
            "roles": user._careos_role_keys(),
            "is_system": user.has_group("base.group_system"),
            "company": user.company_id.name,
            "branch": {"id": current.id, "name": current.name} if current else False,
            "department": user.careos_department_id.name or False,
            "branches": [{"id": b.id, "name": b.name} for b in branches],
        }

    @api.model
    def careos_switch_branch(self, branch_id):
        user = self.env.user
        branch = user.careos_branch_ids.filtered(lambda b: b.id == branch_id and b.active)
        if not branch:
            raise AccessError(_("You are not assigned to this branch."))
        # Users may change their own branch context but not their allowed set.
        user.sudo().careos_branch_id = branch
        return {"id": branch.id, "name": branch.name}
