from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.careos_base.models.authorization import require_role

VIEW_ROLES = {"manager", "admin", "finance"}
ALERT_FACTOR = 2.0          # a department at ≥ 2× the branch no-show rate is flagged
ALERT_MIN_APPOINTMENTS = 3  # …but only with enough bookings to mean something


def _pct_change(current, previous):
    if not previous:
        return None
    return (current - previous) / previous * 100


class CareosAnalytics(models.AbstractModel):
    """Manager Workspace and Analytics. Every figure is computed from live
    appointments, queue tickets and posted invoices at the current branch.
    Reads use sudo after the role check because managers see aggregates, not
    individual clinical or accounting records."""

    _name = "careos.analytics"
    _description = "CareOS Analytics"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @api.model
    def _careos_context(self):
        require_role(self.env, VIEW_ROLES, _("Analytics are available to managers, finance and administrators."))
        branch = self.env.user.careos_branch_id
        if not branch:
            raise UserError(_("Select a branch first."))
        return branch

    @api.model
    def _careos_range(self, branch, date_from, date_to):
        """UTC-naive bounds for branch-local dates [date_from, date_to]."""
        start, _end = branch._careos_day_bounds(date_from)
        _start, end = branch._careos_day_bounds(date_to)
        return start, end

    @api.model
    def _careos_appointments(self, branch, date_from, date_to):
        start, end = self._careos_range(branch, date_from, date_to)
        return self.env["careos.appointment"].sudo().search([
            ("branch_id", "=", branch.id), ("start", ">=", start), ("start", "<", end),
        ])

    @api.model
    def _careos_invoices(self, branch, date_from, date_to):
        return self.env["account.move"].sudo().search([
            ("careos_branch_id", "=", branch.id), ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("invoice_date", ">=", date_from), ("invoice_date", "<=", date_to),
        ])

    @staticmethod
    def _revenue(moves):
        return sum(moves.mapped("amount_untaxed_signed"))

    @staticmethod
    def _no_show_rate(appointments):
        attended = appointments.filtered(lambda a: a.state in ("done", "in_progress", "checked_in", "no_show"))
        return (len(attended.filtered(lambda a: a.state == "no_show")) / len(attended) * 100) if attended else 0.0

    @staticmethod
    def _department(appointment):
        return appointment.provider_id.department_id.name or appointment.provider_id.specialty or _("Unassigned")

    @staticmethod
    def _bars(rows, value_key="value", fmt=None):
        """Attach a 0–100 width relative to the largest value."""
        top = max([r[value_key] for r in rows] or [0]) or 1
        for row in rows:
            row["pct"] = round(row[value_key] / top * 100, 1)
            row["label"] = fmt(row[value_key]) if fmt else row[value_key]
        return rows

    # ------------------------------------------------------------------
    # Manager Workspace
    # ------------------------------------------------------------------

    @api.model
    def careos_manager_dashboard(self):
        branch = self._careos_context()
        currency = branch.company_id.currency_id
        today = branch._careos_today()
        month_start = today.replace(day=1)
        prev_end = month_start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        prev_same_day = min(prev_start + (today - month_start), prev_end)

        appts = self._careos_appointments(branch, month_start, today)
        prev_appts = self._careos_appointments(branch, prev_start, prev_same_day)
        revenue = self._revenue(self._careos_invoices(branch, month_start, today))
        prev_revenue = self._revenue(self._careos_invoices(branch, prev_start, prev_same_day))
        visits = len(appts.filtered(lambda a: a.state == "done"))
        prev_visits = len(prev_appts.filtered(lambda a: a.state == "done"))
        no_show = self._no_show_rate(appts)
        prev_no_show = self._no_show_rate(prev_appts)
        unpaid = self.env["account.move"].sudo().search([
            ("careos_branch_id", "=", branch.id), ("state", "=", "posted"), ("move_type", "=", "out_invoice"),
            ("payment_state", "in", ("not_paid", "partial")),
        ])
        outstanding = sum(unpaid.mapped("amount_residual"))

        def money(value):
            return f"{value:,.0f} {currency.symbol}"

        def delta(change, good_when_up=True, unit="%"):
            if change is None:
                return {"text": _("No data last month"), "tone": ""}
            up = change >= 0
            good = up == good_when_up
            sign = "+" if up else "−"
            return {"text": _("%(sign)s%(value).1f%(unit)s vs last month", sign=sign, value=abs(change), unit=unit),
                    "tone": "up" if good else "down"}

        kpis = [
            {"key": "revenue", "label": _("Revenue MTD"), "value": money(revenue), "delta": delta(_pct_change(revenue, prev_revenue)),
             "screen": "analytics", "tab": "finance"},
            {"key": "visits", "label": _("Patient visits"), "value": f"{visits:,}", "delta": delta(_pct_change(visits, prev_visits)),
             "screen": "analytics", "tab": "patients"},
            {"key": "no_show", "label": _("No-show rate"), "value": f"{no_show:.1f}%",
             "delta": delta(no_show - prev_no_show if prev_appts else None, good_when_up=False, unit="pp"),
             "screen": "analytics", "tab": "operations"},
            {"key": "outstanding", "label": _("Outstanding balance"), "value": money(outstanding),
             "delta": {"text": _("%s unpaid invoices", len(unpaid)), "tone": "down" if unpaid else ""}, "screen": "invoices"},
        ]

        # Revenue by department (invoice lines of visits this month).
        by_dept = defaultdict(float)
        for move in self._careos_invoices(branch, month_start, today):
            dept = self._department(move.careos_appointment_id) if move.careos_appointment_id else _("Unassigned")
            by_dept[dept] += move.amount_untaxed_signed
        dept_revenue = self._bars(sorted(
            [{"name": name, "value": value} for name, value in by_dept.items()], key=lambda r: -r["value"]), fmt=money)

        # Doctor utilization: booked minutes vs opening minutes this month.
        open_minutes = branch._careos_open_minutes(month_start, today) or 1
        utilization = []
        for provider in self.env["careos.provider"].sudo().search([("branch_ids", "in", branch.ids)]):
            booked = sum(appts.filtered(lambda a: a.provider_id == provider and a.state not in ("cancelled",)).mapped("duration"))
            utilization.append({"name": provider.name, "value": round(booked / open_minutes * 100, 1)})
        utilization.sort(key=lambda r: -r["value"])
        self._bars(utilization, fmt=lambda v: f"{v:.0f}%")

        return {
            "branch": branch.name,
            "period": _("Month to date"),
            "kpis": kpis,
            "alert": self._careos_no_show_alert(branch),
            "dept_revenue": dept_revenue,
            "utilization": utilization,
        }

    @api.model
    def _careos_no_show_alert(self, branch):
        """The department with the highest no-show rate this week when it is at
        least twice the branch rate (prototype "Operational alert")."""
        today = branch._careos_today()
        week = self._careos_appointments(branch, today - timedelta(days=6), today)
        branch_rate = self._no_show_rate(week)
        by_dept = defaultdict(lambda: self.env["careos.appointment"])
        for appointment in week:
            by_dept[self._department(appointment)] |= appointment
        worst = None
        for dept, appts in by_dept.items():
            if len(appts) < ALERT_MIN_APPOINTMENTS:
                continue
            rate = self._no_show_rate(appts)
            if branch_rate and rate >= ALERT_FACTOR * branch_rate and (not worst or rate > worst[1]):
                worst = (dept, rate)
        if not worst:
            return False
        return {
            "department": worst[0],
            "text": _("%(dept)s no-show rate is %(ratio).1f× the branch average this week (%(rate).1f%% vs %(avg).1f%%).",
                      dept=worst[0], ratio=worst[1] / branch_rate, rate=worst[1], avg=branch_rate),
        }

    @api.model
    def _careos_cron_insights(self):
        """Daily: tell managers about an elevated no-show rate."""
        Notification = self.env["careos.notification"]
        for branch in self.env["careos.branch"].search([]):
            alert = self.sudo()._careos_no_show_alert(branch)
            if alert:
                Notification._careos_notify(
                    Notification._careos_users_with_roles(["manager"], branch),
                    _("Insight: %s no-show rate elevated", alert["department"]), body=alert["text"], kind="insight",
                    screen="analytics", dedupe_key=f"noshow-{branch.id}-{alert['department']}",
                )

    # ------------------------------------------------------------------
    # Analytics screen
    # ------------------------------------------------------------------

    @api.model
    def careos_analytics(self, tab="operations", days=30):
        branch = self._careos_context()
        today = branch._careos_today()
        date_from = today - timedelta(days=days - 1)
        currency = branch.company_id.currency_id
        result = {"branch": branch.name, "days": days, "tab": tab}
        if tab == "operations":
            appts = self._careos_appointments(branch, date_from, today)
            groups = defaultdict(lambda: self.env["careos.appointment"])
            for appointment in appts:
                groups[self._department(appointment)] |= appointment
            branch_rate = self._no_show_rate(appts)
            no_show = [{"name": d, "value": round(self._no_show_rate(a), 1),
                        "flag": branch_rate and self._no_show_rate(a) >= ALERT_FACTOR * branch_rate and len(a) >= ALERT_MIN_APPOINTMENTS}
                       for d, a in groups.items()]
            no_show.sort(key=lambda r: -r["value"])
            tickets = self.env["careos.queue.ticket"].sudo().search([
                ("branch_id", "=", branch.id), ("queue_date", ">=", date_from), ("started_at", "!=", False),
            ])
            waits = defaultdict(list)
            for ticket in tickets:
                waits[self._department(ticket.appointment_id)].append(
                    (ticket.started_at - ticket.checked_in_at).total_seconds() / 60)
            wait_rows = [{"name": d, "value": round(sum(v) / len(v), 1), "count": len(v)} for d, v in waits.items()]
            wait_rows.sort(key=lambda r: -r["value"])
            result.update({
                "branch_no_show": round(branch_rate, 1),
                "no_show": self._bars(no_show, fmt=lambda v: f"{v:.1f}%"),
                "wait": self._bars(wait_rows, fmt=lambda v: f"{v:.0f} min"),
            })
        elif tab == "finance":
            by_line = defaultdict(float)
            for move in self._careos_invoices(branch, date_from, today):
                sign = -1 if move.move_type == "out_refund" else 1
                for line in move.invoice_line_ids:
                    if line.careos_lab_order_id:
                        key = _("Laboratory")
                    elif line.careos_prescription_line_id:
                        key = _("Pharmacy dispensing")
                    elif line.careos_appointment_id:
                        key = _("Consultations")
                    else:
                        key = _("Other")
                    by_line[key] += sign * line.price_subtotal
            rows = sorted([{"name": k, "value": v} for k, v in by_line.items()], key=lambda r: -r["value"])
            result.update({
                "revenue_by_service": self._bars(rows, fmt=lambda v: f"{v:,.0f} {currency.symbol}"),
                "total": f"{sum(by_line.values()):,.0f} {currency.symbol}",
            })
        elif tab == "patients":
            weeks = []
            done = self.env["careos.appointment"].sudo().search([("branch_id", "=", branch.id), ("state", "=", "done")])
            first_visit = {}
            for appointment in done.sorted("start"):
                first_visit.setdefault(appointment.patient_id.id, appointment.start)
            week_start = today - timedelta(days=(today.weekday() + 1) % 7)  # weeks start on Sunday
            for index in range(3, -1, -1):
                start_day = week_start - timedelta(weeks=index)
                start, end = self._careos_range(branch, start_day, start_day + timedelta(days=6))
                visits = done.filtered(lambda a: start <= a.start < end)
                patients = visits.patient_id
                new = [p for p in patients if start <= first_visit[p.id] < end]
                weeks.append({"week": _("Week of %s", start_day.strftime("%b %d")), "new": len(new),
                              "returning": len(patients) - len(new)})
            result["patient_growth"] = weeks
        return result
