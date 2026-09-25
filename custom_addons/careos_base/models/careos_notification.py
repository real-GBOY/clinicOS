from odoo import api, fields, models

from .res_users import CAREOS_ROLES

KINDS = [("info", "Info"), ("success", "Success"), ("warning", "Warning"), ("danger", "Alert"), ("insight", "Insight")]


class CareosNotification(models.Model):
    """In-app notification for one staff member (the prototype bell).

    Producers call ``_careos_notify`` from business events (lab result ready,
    overdue invoice, low stock…). Each user only ever sees their own rows.
    """

    _name = "careos.notification"
    _description = "CareOS Notification"
    _order = "create_date desc, id desc"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    title = fields.Char(required=True)
    body = fields.Char()
    kind = fields.Selection(KINDS, required=True, default="info")
    screen = fields.Char(help="CareOS screen to open, e.g. 'patient'.")
    res_id = fields.Integer(help="Record id passed to the screen as resId.")
    is_read = fields.Boolean(index=True)
    dedupe_key = fields.Char(index=True, help="Suppresses repeat notifications for the same event.")

    @api.model
    def _careos_notify(self, users, title, body="", kind="info", screen=None, res_id=None, dedupe_key=None):
        """Create one notification per user (system-side, sudo). With a
        ``dedupe_key``, users who already have an unread notification with the
        same key are skipped."""
        users = users.filtered(lambda u: u.active and not u.share)
        if dedupe_key:
            existing = self.sudo().search([("dedupe_key", "=", dedupe_key), ("is_read", "=", False),
                                            ("user_id", "in", users.ids)])
            users -= existing.user_id
        return self.sudo().create([{
            "user_id": user.id, "title": title, "body": body, "kind": kind,
            "screen": screen, "res_id": res_id or 0, "dedupe_key": dedupe_key,
        } for user in users])

    @api.model
    def _careos_users_with_roles(self, role_keys, branch=None):
        """Active CareOS users holding any of ``role_keys`` (and assigned to
        ``branch`` when given)."""
        groups = self.env["res.groups"]
        for key in role_keys:
            groups |= self.env.ref(CAREOS_ROLES[key])
        users = groups.sudo().all_user_ids.filtered(lambda u: u.active and not u.share)
        if branch:
            users = users.filtered(lambda u: branch in u.careos_branch_ids)
        return users

    @api.model
    def careos_inbox(self, limit=20):
        """The current user's latest notifications and unread count."""
        mine = self.search([("user_id", "=", self.env.uid)], limit=limit)
        return {
            "unread": self.search_count([("user_id", "=", self.env.uid), ("is_read", "=", False)]),
            "items": [{
                "id": n.id, "title": n.title, "body": n.body or "", "kind": n.kind, "screen": n.screen or False,
                "res_id": n.res_id or False, "is_read": n.is_read, "date": fields.Datetime.to_string(n.create_date),
            } for n in mine],
        }

    def careos_mark_read(self):
        self.filtered(lambda n: n.user_id == self.env.user).write({"is_read": True})
        return True

    @api.model
    def careos_mark_all_read(self):
        self.search([("user_id", "=", self.env.uid), ("is_read", "=", False)]).write({"is_read": True})
        return True
