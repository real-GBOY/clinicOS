from odoo import fields, models


class CareosRoom(models.Model):
    """A consultation or procedure room at a branch. Rooms are a bookable
    resource: two appointments cannot hold the same room at the same time."""

    _name = "careos.room"
    _description = "Clinic Room"
    _order = "branch_id, sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    branch_id = fields.Many2one("careos.branch", required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one(related="branch_id.company_id", store=True, index=True)

    _name_branch_uniq = models.Constraint("UNIQUE(name, branch_id)", "Room names must be unique within a branch.")
