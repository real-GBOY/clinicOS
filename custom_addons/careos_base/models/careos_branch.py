from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
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
    # Opening hours (setup guide "Configure working hours"); weekdays use
    # Python numbering, Monday = 0 … Sunday = 6. Default: Sun–Thu, 09:00–17:00.
    work_days = fields.Char(default="0,1,2,3,6", help="Comma-separated weekday numbers, Monday = 0.")
    work_start = fields.Float(default=9.0, help="Opening time, hours (9.5 = 09:30).")
    work_end = fields.Float(default=17.0, help="Closing time, hours.")

    @api.constrains("work_start", "work_end", "work_days")
    def _check_hours(self):
        for branch in self:
            if not 0 <= branch.work_start < branch.work_end <= 24:
                raise ValidationError(_("Opening time must be before closing time, within the day."))
            try:
                days = [int(d) for d in (branch.work_days or "").split(",") if d.strip()]
            except ValueError:
                days = [-1]
            if any(d not in range(7) for d in days):
                raise ValidationError(_("Working days must be weekday numbers 0–6."))

    def _careos_work_days(self):
        self.ensure_one()
        return {int(d) for d in (self.work_days or "").split(",") if d.strip()}

    def _careos_open_minutes(self, date_from, date_to):
        """Opening minutes between two dates (inclusive)."""
        self.ensure_one()
        days = self._careos_work_days()
        per_day = (self.work_end - self.work_start) * 60
        total, day = 0, date_from
        while day <= date_to:
            if day.weekday() in days:
                total += per_day
            day += timedelta(days=1)
        return total

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A branch code must be unique within the organization."
    )

    # ------------------------------------------------------------------
    # Branch-local time. Operational days ("today's appointments") are
    # defined by the branch timezone, not the server's or the browser's.
    # ------------------------------------------------------------------

    def _careos_tz(self):
        self.ensure_one()
        return pytz.timezone(self.timezone or "UTC")

    def _careos_today(self):
        """The current date at this branch."""
        return datetime.now(pytz.utc).astimezone(self._careos_tz()).date()

    def _careos_day_bounds(self, day=None):
        """UTC-naive [start, end) datetimes covering ``day`` in branch time."""
        tz = self._careos_tz()
        day = day or self._careos_today()
        start = tz.localize(datetime.combine(day, time.min))
        end = tz.localize(datetime.combine(day + timedelta(days=1), time.min))
        return start.astimezone(pytz.utc).replace(tzinfo=None), end.astimezone(pytz.utc).replace(tzinfo=None)

    def _careos_local_date(self, dt):
        """Branch-local date of a UTC-naive datetime."""
        return pytz.utc.localize(dt).astimezone(self._careos_tz()).date()

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
