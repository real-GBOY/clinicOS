from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.careos_base.models.res_users import CAREOS_ROLES

WEEKDAYS = [(6, "Sun"), (0, "Mon"), (1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri"), (5, "Sat")]
INVITE_ROLES = ["reception", "doctor", "nurse", "lab", "pharmacy", "finance", "manager", "admin"]


class CareosSetup(models.AbstractModel):
    """Setup guide (prototype): eight steps that configure a clinic group.
    Each step reads the current configuration and saves real records."""

    _name = "careos.setup"
    _description = "CareOS Setup Guide"

    @api.model
    def _careos_require_admin(self):
        user = self.env.user
        if not (self.env.su or user.has_group("careos_base.group_careos_admin") or user.has_group("base.group_system")):
            raise AccessError(_("Only administrators can run the setup guide."))

    @api.model
    def _careos_branch(self):
        branch = self.env.user.careos_branch_id or self.env["careos.branch"].search([], limit=1)
        return branch.sudo()

    @api.model
    def careos_setup_state(self):
        self._careos_require_admin()
        company = self.env.company.sudo()
        branch = self._careos_branch()
        tests = self.env["careos.lab.test"].sudo().search([])
        return {
            "organization": {"name": company.name, "country_id": company.country_id.id or False,
                             "countries": [{"id": c.id, "name": c.name} for c in self.env["res.country"].search([])]},
            "branch": {"id": branch.id or False, "name": branch.name or "", "code": branch.code or "",
                       "timezone": branch.timezone or "UTC",
                       "timezones": [tz for tz, _label in self.env["careos.branch"]._fields["timezone"].selection(self.env["careos.branch"])]},
            "departments": [d.name for d in branch.department_ids],
            "providers": [{"id": p.id, "name": p.name, "specialty": p.specialty or "",
                           "login": p.user_id.login or ""} for p in self.env["careos.provider"].sudo().search([("branch_ids", "in", branch.ids)])],
            "hours": {"days": sorted(branch._careos_work_days()) if branch else [0, 1, 2, 3, 6],
                      "start": branch.work_start if branch else 9.0, "end": branch.work_end if branch else 17.0,
                      "weekdays": WEEKDAYS},
            "types": [{"id": t.id, "name": t.name, "duration": t.duration} for t in self.env["careos.appointment.type"].sudo().search([])],
            "prices": {
                "types": [{"id": t.id, "name": t.name, "price": t.price} for t in self.env["careos.appointment.type"].sudo().search([])],
                "tests": [{"id": t.id, "name": t.name, "price": t.price} for t in tests],
            },
            "staff": [{"name": u.name, "login": u.login, "roles": u._careos_role_keys()}
                      for u in self.env["res.users"].sudo().search([("share", "=", False), ("careos_branch_ids", "in", branch.ids)])],
            "roles": INVITE_ROLES,
            "currency": company.currency_id.symbol,
        }

    @api.model
    def careos_setup_save(self, step, values):
        """Save one step. Returns the refreshed state."""
        self._careos_require_admin()
        handler = getattr(self, f"_careos_save_{step}", None)
        if not handler:
            raise ValidationError(_("Unknown setup step."))
        handler(values or {})
        return self.careos_setup_state()

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _careos_save_organization(self, values):
        name = (values.get("name") or "").strip()
        if not name:
            raise ValidationError(_("Enter the organization name."))
        self.env.company.sudo().write({"name": name, "country_id": values.get("country_id") or False})

    def _careos_save_branch(self, values):
        name = (values.get("name") or "").strip()
        if not name:
            raise ValidationError(_("Enter the branch name."))
        vals = {"name": name, "code": (values.get("code") or name[:3]).upper(), "timezone": values.get("timezone") or "UTC"}
        branch = self._careos_branch()
        if branch:
            branch.write(vals)
        else:
            branch = self.env["careos.branch"].sudo().create(vals)
        user = self.env.user.sudo()
        user.careos_branch_ids = [(4, branch.id)]
        user.careos_branch_id = branch

    def _careos_save_departments(self, values):
        branch = self._careos_branch()
        names = [n.strip() for n in values.get("names", []) if n and n.strip()]
        existing = {d.name: d for d in branch.department_ids}
        for name in names:
            if name not in existing:
                self.env["careos.department"].sudo().create({"name": name, "branch_id": branch.id})

    def _careos_save_providers(self, values):
        branch = self._careos_branch()
        for row in values.get("providers", []):
            name = (row.get("name") or "").strip()
            if not name or row.get("id"):
                continue
            provider = self.env["careos.provider"].sudo().create({
                "name": name, "specialty": row.get("specialty") or False, "branch_ids": [(6, 0, branch.ids)],
            })
            if (row.get("email") or "").strip():
                user = self._careos_invite(name, row["email"].strip(), "doctor")
                provider.user_id = user

    def _careos_save_hours(self, values):
        days = [int(d) for d in values.get("days", [])]
        if not days:
            raise ValidationError(_("Choose at least one working day."))
        self._careos_branch().write({
            "work_days": ",".join(str(d) for d in sorted(days)),
            "work_start": float(values.get("start", 9)), "work_end": float(values.get("end", 17)),
        })

    def _careos_save_types(self, values):
        Type = self.env["careos.appointment.type"].sudo()
        for row in values.get("types", []):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            duration = int(row.get("duration") or 30)
            if row.get("id"):
                Type.browse(row["id"]).write({"name": name, "duration": duration})
            else:
                Type.create({"name": name, "duration": duration})

    def _careos_save_prices(self, values):
        for row in values.get("types", []):
            self.env["careos.appointment.type"].sudo().browse(row["id"]).price = float(row.get("price") or 0)
        for row in values.get("tests", []):
            self.env["careos.lab.test"].sudo().browse(row["id"]).price = float(row.get("price") or 0)

    def _careos_save_staff(self, values):
        for row in values.get("invites", []):
            if (row.get("email") or "").strip() and row.get("role") in INVITE_ROLES:
                self._careos_invite((row.get("name") or row["email"]).strip(), row["email"].strip(), row["role"])

    def _careos_invite(self, name, email, role):
        """Create a staff account with a CareOS role at the current branch
        and send the invitation e-mail (set-password link)."""
        Users = self.env["res.users"].sudo()
        if Users.with_context(active_test=False).search_count([("login", "=", email)]):
            raise ValidationError(_("An account already exists for %s.", email))
        branch = self._careos_branch()
        user = Users.with_context(no_reset_password=True).create({
            "name": name, "login": email, "email": email,
            "group_ids": [(6, 0, [self.env.ref(CAREOS_ROLES[role]).id])],
            "careos_branch_ids": [(6, 0, branch.ids)], "careos_branch_id": branch.id,
            "action_id": self.env.ref("careos_base.action_careos_app").id,
        })
        try:
            user.action_reset_password()
        except Exception:  # outgoing mail not configured: the account still exists
            pass
        return user
