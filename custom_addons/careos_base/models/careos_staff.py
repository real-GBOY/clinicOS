import re

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .res_users import CAREOS_ROLES
from .authorization import has_role, require_role

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# What each role is for, shown on the Roles tab. The groups and record rules
# are the control; this text only explains them.
ROLE_INFO = {
    "reception": ("Reception", "Front desk: registration, scheduling and billing at the desk.",
                  ["Register and edit patients", "Book, confirm, cancel and check in appointments",
                   "Run the queue", "Create invoices and take payments"]),
    "doctor": ("Doctor", "Consultations for the doctor's own patients.",
               ["See own schedule and queue", "Write notes and diagnoses, sign off visits",
                "Prescribe and order lab tests", "Review lab results"]),
    "nurse": ("Nurse", "Clinical support at the branch.",
              ["Record vitals", "Read clinical records", "Call patients from the queue",
               "Collect lab samples"]),
    "lab": ("Laboratory", "Laboratory worklist.",
            ["Collect and process samples", "Enter and verify results", "Read lab stock"]),
    "pharmacy": ("Pharmacy", "Dispensing and medicine stock.",
                 ["Dispense issued prescriptions", "Receive stock with batch and expiry",
                  "Low-stock and expiry alerts"]),
    "finance": ("Finance", "Billing, payments and financial reports.",
                ["Create invoices and take payments", "Issue refunds", "Finance analytics"]),
    "manager": ("Manager", "Oversight of the clinic, read-mostly.",
                ["Manager dashboard and analytics", "See appointments, queue and invoices",
                 "Read inventory and staff"]),
    "admin": ("Administrator", "Configuration and staff administration.",
              ["Setup guide and clinic configuration", "Invite staff and assign roles and branches",
               "Enable AI assistance", "Receive stock"]),
}


class CareosStaffLog(models.Model):
    """Who changed whose access, and how. Written only by careos.staff."""

    _name = "careos.staff.log"
    _description = "CareOS Staff Access Change"
    _order = "create_date desc, id desc"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    summary = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)


class CareosStaff(models.AbstractModel):
    """Staff & roles: invite staff, assign roles, branches and department,
    deactivate accounts. Admins manage; managers read their branches."""

    _name = "careos.staff"
    _description = "CareOS Staff Administration"

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @api.model
    def _careos_is_admin(self):
        return has_role(self.env, "admin")

    @api.model
    def _careos_require_admin(self):
        require_role(self.env, "admin", _("Only administrators can manage staff."))

    @api.model
    def _careos_require_viewer(self):
        require_role(self.env, {"admin", "manager"}, _("You do not have access to staff administration."))

    @api.model
    def _careos_scope_domain(self):
        """CareOS staff of the current company; managers only see their branches."""
        domain = [("share", "=", False), ("id", "!=", SUPERUSER_ID), ("company_ids", "in", self.env.company.id),
                  ("all_group_ids", "in", self.env.ref("careos_base.group_careos_user").id)]
        if not self._careos_is_admin():
            domain.append(("careos_branch_ids", "in", self.env.user.careos_branch_ids.ids))
        return domain

    @api.model
    def _careos_get_user(self, user_id):
        member = self.env["res.users"].sudo().with_context(active_test=False).search(
            self._careos_scope_domain() + [("id", "=", int(user_id))], limit=1)
        if not member:
            raise AccessError(_("This staff member is not available to you."))
        return member

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    @api.model
    def _careos_status(self, user):
        if not user.active:
            return "inactive"
        return "active" if user.login_date else "invited"

    @api.model
    def _careos_row(self, user):
        status = self._careos_status(user)
        return {
            "id": user.id,
            "name": user.name,
            "login": user.login,
            "email": user.email or "",
            "roles": user._careos_role_keys(),
            "branches": [{"id": b.id, "name": b.name} for b in user.careos_branch_ids],
            "branch_id": user.careos_branch_id.id or False,
            "department": {"id": user.careos_department_id.id, "name": user.careos_department_id.name}
            if user.careos_department_id else False,
            "last_login": fields.Datetime.to_string(user.login_date) if user.login_date else False,
            "status": status,
            "is_self": user == self.env.user,
        }

    @api.model
    def careos_staff_overview(self, query="", status="active", role=False):
        self._careos_require_viewer()
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        everyone = Users.search(self._careos_scope_domain(), order="name")
        rows = [self._careos_row(u) for u in everyone]
        counts = {key: sum(1 for r in rows if r["status"] == key) for key in ("active", "invited", "inactive")}
        role_counts = {key: sum(1 for r in rows if key in r["roles"] and r["status"] != "inactive") for key in CAREOS_ROLES}

        needle = (query or "").strip().lower()
        shown = [
            r for r in rows
            if (not status or r["status"] == status)
            and (not role or role in r["roles"])
            and (not needle or needle in r["name"].lower() or needle in r["login"].lower() or needle in r["email"].lower())
        ]
        branches = self.env["careos.branch"].sudo().search([("company_id", "=", self.env.company.id)])
        if not self._careos_is_admin():
            branches &= self.env.user.careos_branch_ids
        return {
            "can_manage": self._careos_is_admin(),
            "kpis": [
                {"key": "active", "label": "Active staff", "value": counts["active"]},
                {"key": "invited", "label": "Invitations pending", "value": counts["invited"],
                 "tone": "warning" if counts["invited"] else False},
                {"key": "inactive", "label": "Deactivated", "value": counts["inactive"]},
                {"key": "admins", "label": "Administrators", "value": role_counts["admin"]},
            ],
            "counts": counts,
            "staff": shown,
            "roles": [
                {"key": key, "label": info[0], "description": info[1], "capabilities": info[2],
                 "count": role_counts[key]}
                for key, info in ROLE_INFO.items()
            ],
            "branches": [{"id": b.id, "name": b.name} for b in branches],
            "departments": [{"id": d.id, "name": d.name, "branch_id": d.branch_id.id}
                            for d in self.env["careos.department"].sudo().search([("branch_id", "in", branches.ids)])],
        }

    @api.model
    def careos_staff_detail(self, user_id):
        self._careos_require_viewer()
        user = self._careos_get_user(user_id)
        logs = self.env["careos.staff.log"].sudo().search([("user_id", "=", user.id)], limit=20)
        return dict(self._careos_row(user), history=[
            {"id": log.id, "summary": log.summary, "actor": log.actor_id.name,
             "date": fields.Datetime.to_string(log.create_date)} for log in logs
        ])

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    @api.model
    def _careos_clean(self, values, existing=None):
        """Validate an access payload; returns (name, email, roles, branches, current, department)."""
        name = (values.get("name") or "").strip()
        email = (values.get("email") or "").strip().lower()
        if not name:
            raise ValidationError(_("Enter the staff member's name."))
        # Existing accounts may sign in with a plain login (e.g. "nurse"): only a
        # new or changed sign-in has to be an e-mail address.
        unchanged = existing and email == (existing.login or "").lower()
        if not unchanged and not EMAIL_RE.match(email):
            raise ValidationError(_("Enter a valid e-mail address."))
        roles = [r for r in values.get("roles") or [] if r in CAREOS_ROLES]
        if not roles or len(roles) != len(values.get("roles") or []):
            raise ValidationError(_("Choose at least one valid role. To remove all access, deactivate the account."))
        Branch = self.env["careos.branch"].sudo()
        branches = Branch.browse([int(b) for b in values.get("branch_ids") or []]).exists()
        branches = branches.filtered(lambda b: b.company_id == self.env.company)
        if not branches or len(branches) != len(values.get("branch_ids") or []):
            raise ValidationError(_("Choose at least one branch."))
        current = Branch.browse(int(values["branch_id"])) if values.get("branch_id") else branches[:1]
        if current not in branches:
            raise ValidationError(_("The current branch must be one of the selected branches."))
        department = self.env["careos.department"].sudo().browse(int(values["department_id"])) \
            if values.get("department_id") else self.env["careos.department"]
        if department and department.branch_id not in branches:
            raise ValidationError(_("The department must belong to one of the selected branches."))
        clash = self.env["res.users"].sudo().with_context(active_test=False).search_count(
            [("login", "=", email)] + ([("id", "!=", existing.id)] if existing else []))
        if clash:
            raise ValidationError(_("An account already exists for %s.", email))
        return name, email, roles, branches, current, department

    @api.model
    def _careos_active_admins(self):
        admin = self.env.ref("careos_base.group_careos_admin")
        return self.env["res.users"].sudo().search([("share", "=", False), ("all_group_ids", "in", admin.id)])

    @api.model
    def _careos_role_commands(self, member, roles):
        commands = []
        for key, xmlid in CAREOS_ROLES.items():
            group = self.env.ref(xmlid)
            if key in roles and group not in member.group_ids:
                commands.append((4, group.id))
            elif key not in roles and group in member.group_ids:
                commands.append((3, group.id))
        return commands

    @api.model
    def _careos_log(self, member, summary):
        self.env["careos.staff.log"].sudo().create({"user_id": member.id, "actor_id": self.env.user.id, "summary": summary})

    @api.model
    def _careos_labels(self, roles):
        return ", ".join(ROLE_INFO[r][0] for r in roles) or "—"

    @api.model
    def _careos_send_invite(self, member):
        """Send the set-password invitation. Returns False if mail is not configured."""
        try:
            with self.env.cr.savepoint():
                member.with_context(create_user=True).action_reset_password()
            return True
        except Exception:  # noqa: BLE001 - no outgoing mail server: the account still exists
            return False

    @api.model
    def _careos_create_staff(self, values):
        """Create a staff account and send its invitation. Used by the Staff
        screen and the setup guide; callers check the permission."""
        name, email, roles, branches, current, department = self._careos_clean(values)
        member = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
            "name": name, "login": email, "email": email,
            "group_ids": [(6, 0, [self.env.ref(CAREOS_ROLES[r]).id for r in roles])],
            "company_id": self.env.company.id, "company_ids": [(6, 0, self.env.company.ids)],
            "careos_branch_ids": [(6, 0, branches.ids)], "careos_branch_id": current.id,
            "careos_department_id": department.id or False,
            "action_id": self.env.ref("careos_base.action_careos_app").id,
        })
        self._careos_log(member, _("Invited as %(roles)s at %(branches)s",
                                 roles=self._careos_labels(roles), branches=", ".join(branches.mapped("name"))))
        self._careos_send_invite(member)
        return member

    @api.model
    def careos_staff_invite(self, values):
        self._careos_require_admin()
        member = self._careos_create_staff(values or {})
        return self.careos_staff_detail(member.id)

    @api.model
    def careos_staff_save(self, user_id, values):
        self._careos_require_admin()
        member = self._careos_get_user(user_id)
        name, email, roles, branches, current, department = self._careos_clean(values or {}, existing=member)
        before = member._careos_role_keys()
        if member == self.env.user and "admin" in before and "admin" not in roles:
            raise ValidationError(_("You cannot remove your own administrator role."))
        changes = []
        if set(before) != set(roles):
            changes.append(_("Roles: %(old)s → %(new)s", old=self._careos_labels(before), new=self._careos_labels(roles)))
        if member.careos_branch_ids != branches:
            changes.append(_("Branches: %s", ", ".join(branches.mapped("name"))))
        if member.careos_department_id != department:
            changes.append(_("Department: %s", department.name or "—"))
        if (member.name, member.login) != (name, email):
            changes.append(_("Details updated"))
        member.write({
            "name": name, "login": email, "email": email if EMAIL_RE.match(email) else member.email,
            "group_ids": self._careos_role_commands(member, roles),
            "careos_branch_ids": [(6, 0, branches.ids)], "careos_branch_id": current.id,
            "careos_department_id": department.id or False,
        })
        if not self._careos_active_admins():
            raise ValidationError(_("CareOS needs at least one active administrator."))
        if changes:
            self._careos_log(member, "; ".join(changes))
        return self.careos_staff_detail(member.id)

    @api.model
    def careos_staff_set_active(self, user_id, active):
        self._careos_require_admin()
        member = self._careos_get_user(user_id)
        if member == self.env.user and not active:
            raise ValidationError(_("You cannot deactivate your own account."))
        if bool(active) != member.active:
            member.active = bool(active)
            if not self._careos_active_admins():
                raise ValidationError(_("CareOS needs at least one active administrator."))
            self._careos_log(member, _("Account reactivated") if active else _("Account deactivated"))
        return self.careos_staff_detail(member.id)

    @api.model
    def careos_staff_resend_invite(self, user_id):
        self._careos_require_admin()
        member = self._careos_get_user(user_id)
        if not member.active:
            raise ValidationError(_("Reactivate the account before sending an invitation."))
        if not self._careos_send_invite(member):
            raise ValidationError(_("The invitation could not be sent. Check the outgoing mail server."))
        self._careos_log(member, _("Invitation sent"))
        return self.careos_staff_detail(member.id)
