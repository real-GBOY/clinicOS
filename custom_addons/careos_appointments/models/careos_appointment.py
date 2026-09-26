from datetime import date, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain

from odoo.addons.careos_base.models.authorization import has_role

STATES = [
    ("draft", "Draft"),
    ("confirmed", "Confirmed"),
    ("checked_in", "Checked-in"),
    ("in_progress", "In Progress"),
    ("done", "Completed"),
    ("cancelled", "Cancelled"),
    ("no_show", "No-show"),
]

# The appointment lifecycle from the CareOS specification (§6):
#   Draft → Confirmed → Checked-in → In Progress → Completed
#   Confirmed → Cancelled · Confirmed → No-show
# Two additions, documented in docs/domain-model.md: a Draft can be cancelled
# (otherwise it could never leave the book), and a Checked-in patient who
# leaves before being seen becomes a No-show (mirrors the queue's rule).
TRANSITIONS = {
    "confirm": ({"draft"}, "confirmed"),
    "check_in": ({"confirmed"}, "checked_in"),
    "start": ({"checked_in"}, "in_progress"),
    "complete": ({"in_progress"}, "done"),
    "cancel": ({"draft", "confirmed"}, "cancelled"),
    "no_show": ({"confirmed", "checked_in"}, "no_show"),
}

# Which CareOS roles may perform each action. Enforced server-side on top of
# ACLs and record rules (a doctor may write their own appointments, but may
# not check patients in).
ACTION_ROLES = {
    "confirm": ("reception", "admin"),
    "check_in": ("reception",),
    "start": ("reception", "doctor"),
    "complete": ("reception", "doctor"),
    "cancel": ("reception", "admin"),
    "no_show": ("reception",),
    "edit": ("reception", "admin"),
}

# Used in messages only; the UI shows its own button labels.
ACTION_VERBS = {
    "confirm": "confirm",
    "check_in": "check in",
    "start": "start",
    "complete": "complete",
    "cancel": "cancel",
    "no_show": "mark as no-show",
    "edit": "book or reschedule",
}

STATE_TIMESTAMP = {
    "confirmed": "confirmed_at",
    "checked_in": "checked_in_at",
    "in_progress": "started_at",
    "done": "completed_at",
    "cancelled": "cancelled_at",
    "no_show": "no_show_at",
}

# States that occupy the provider, room and patient for the booked interval.
BLOCKING_STATES = ("draft", "confirmed", "checked_in", "in_progress")
EDITABLE_STATES = ("draft", "confirmed")
SCHEDULE_FIELDS = {"start", "duration", "provider_id", "room_id", "branch_id", "type_id"}
MAX_DURATION = 8 * 60

# Order of lifecycle events that share a timestamp (tie-breaker for timelines).
HISTORY_RANK = {
    "created": 0, "confirmed_at": 1, "checked_in_at": 2, "called": 3,
    "started_at": 4, "completed_at": 5, "cancelled_at": 6, "no_show_at": 7,
}

class CareosAppointment(models.Model):
    _name = "careos.appointment"
    _description = "Appointment"
    _inherit = ["mail.thread"]
    _order = "start, id"
    _rec_names_search = ["name", "patient_id.name", "patient_id.ref"]

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, index=True, default=lambda self: _("New"))
    patient_id = fields.Many2one("careos.patient", required=True, index=True, ondelete="restrict", tracking=True)
    provider_id = fields.Many2one("careos.provider", required=True, index=True, ondelete="restrict", tracking=True)
    type_id = fields.Many2one("careos.appointment.type", string="Visit type", required=True, ondelete="restrict", tracking=True)
    branch_id = fields.Many2one(
        "careos.branch", required=True, index=True, ondelete="restrict", tracking=True,
        default=lambda self: self.env.user.careos_branch_id,
    )
    company_id = fields.Many2one(related="branch_id.company_id", store=True, index=True)
    room_id = fields.Many2one("careos.room", ondelete="restrict", tracking=True)

    start = fields.Datetime(required=True, index=True, tracking=True)
    duration = fields.Integer(
        string="Duration (minutes)", compute="_compute_duration", store=True, readonly=False, precompute=True,
    )
    stop = fields.Datetime(compute="_compute_stop", store=True, index=True)

    state = fields.Selection(STATES, required=True, default="draft", index=True, tracking=True, copy=False)
    reason = fields.Char(string="Reason for visit")
    notes = fields.Text(string="Front-desk notes")
    cancel_reason = fields.Char(tracking=True, copy=False)

    confirmed_at = fields.Datetime(readonly=True, copy=False)
    checked_in_at = fields.Datetime(readonly=True, copy=False)
    started_at = fields.Datetime(readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    cancelled_at = fields.Datetime(readonly=True, copy=False)
    no_show_at = fields.Datetime(readonly=True, copy=False)

    _name_company_uniq = models.Constraint("UNIQUE(name, company_id)", "Appointment references must be unique.")
    _branch_start_idx = models.Index("(branch_id, start)")
    _provider_start_idx = models.Index("(provider_id, start)")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("type_id")
    def _compute_duration(self):
        for appointment in self:
            if appointment.type_id and not appointment.duration:
                appointment.duration = appointment.type_id.duration

    @api.depends("start", "duration")
    def _compute_stop(self):
        for appointment in self:
            if appointment.start and appointment.duration:
                appointment.stop = appointment.start + timedelta(minutes=appointment.duration)
            else:
                appointment.stop = appointment.start

    def _compute_display_name(self):
        for appointment in self:
            appointment.display_name = f"{appointment.name} · {appointment.patient_id.name}"

    # ------------------------------------------------------------------
    # Constraints — scheduling rules
    # ------------------------------------------------------------------

    @api.constrains("duration")
    def _check_duration(self):
        for appointment in self:
            if not 0 < appointment.duration <= MAX_DURATION:
                raise ValidationError(_("An appointment must last between 1 minute and 8 hours."))

    @api.constrains("branch_id", "provider_id", "room_id", "patient_id")
    def _check_consistency(self):
        for appointment in self:
            if appointment.branch_id not in appointment.provider_id.branch_ids:
                raise ValidationError(_("%(provider)s does not practice at %(branch)s.",
                                        provider=appointment.provider_id.name, branch=appointment.branch_id.name))
            if appointment.room_id and appointment.room_id.branch_id != appointment.branch_id:
                raise ValidationError(_("The room must be at the appointment's branch."))
            if appointment.patient_id.company_id != appointment.company_id:
                raise ValidationError(_("The patient belongs to another organization."))

    @api.constrains("start", "stop", "provider_id", "room_id", "patient_id", "state")
    def _check_conflicts(self):
        """No double-booking of a provider, a room or a patient. Checked with
        sudo so bookings the current user cannot see (another branch, another
        doctor's list) still count; the message reveals no patient data."""
        Appointment = self.sudo()
        for appointment in self.filtered(lambda a: a.state in BLOCKING_STATES):
            overlap = Domain([
                ("id", "!=", appointment.id),
                ("state", "in", BLOCKING_STATES),
                ("start", "<", appointment.stop),
                ("stop", ">", appointment.start),
            ])
            checks = [
                ("provider_id", _("%s is already booked at this time.", appointment.provider_id.name)),
                ("room_id", _("%s is already booked at this time.", appointment.room_id.name)),
                ("patient_id", _("This patient already has an appointment at this time.")),
            ]
            for field_name, message in checks:
                record = appointment[field_name]
                if record and Appointment.search_count(overlap & Domain(field_name, "=", record.id), limit=1):
                    raise ValidationError(message)

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("state", "draft") != "draft":
                raise UserError(_("Appointments are created as drafts; use Confirm to confirm them."))
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("careos.appointment") or _("New")
        appointments = super().create(vals_list)
        appointments._check_bookable_date()
        return appointments

    def write(self, vals):
        if "state" in vals and not self.env.context.get("careos_transition"):
            raise UserError(_("Appointment status changes only through its workflow actions."))
        if SCHEDULE_FIELDS & vals.keys() or "patient_id" in vals:
            locked = self.filtered(lambda a: a.state not in EDITABLE_STATES)
            if locked:
                raise UserError(_("%s can no longer be rescheduled.", locked[0].name))
            if "patient_id" in vals and self.filtered(lambda a: a.state != "draft"):
                raise UserError(_("The patient of a confirmed appointment cannot be changed. Cancel and rebook instead."))
        result = super().write(vals)
        if "start" in vals or "branch_id" in vals:
            self._check_bookable_date()
        return result

    def _check_bookable_date(self):
        """New bookings and reschedules cannot land on a past day (same-day
        bookings earlier than now are allowed, e.g. for walk-ins recorded late).
        Historic records can be imported by the system only (superuser with the
        ``careos_import_history`` context), e.g. when migrating a clinic."""
        if self.env.su and self.env.context.get("careos_import_history"):
            return
        for appointment in self:
            branch = appointment.branch_id
            if branch._careos_local_date(appointment.start) < branch._careos_today():
                raise ValidationError(_("Appointments cannot be booked on a past date."))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _careos_user_roles(self):
        return self.env.user._careos_role_keys()

    def _careos_role_allows(self, action):
        return has_role(self.env, ACTION_ROLES[action])

    def _careos_action_blocker(self, action):
        """Why ``action`` cannot run on this appointment now (None if it can).
        Role, state and date rules; ACLs/record rules are checked by the ORM."""
        self.ensure_one()
        sources, _target = TRANSITIONS[action]
        if self.state not in sources:
            return _("%(ref)s is %(state)s; it cannot be %(action)s.",
                     ref=self.name, state=dict(STATES)[self.state], action=ACTION_VERBS[action])
        if action == "check_in" and self.branch_id._careos_local_date(self.start) != self.branch_id._careos_today():
            return _("Patients can only be checked in on the day of their appointment.")
        if action == "no_show" and self.state == "confirmed" and self.start > fields.Datetime.now():
            return _("A patient can only be marked as a no-show after the appointment time.")
        return None

    def _careos_transition(self, action, extra_vals=None):
        if not self._careos_role_allows(action):
            raise AccessError(_("Your role does not allow you to %s appointments.", ACTION_VERBS[action]))
        self.check_access("write")
        for appointment in self:
            blocker = appointment._careos_action_blocker(action)
            if blocker:
                raise UserError(blocker)
        target = TRANSITIONS[action][1]
        vals = {"state": target, STATE_TIMESTAMP[target]: fields.Datetime.now(), **(extra_vals or {})}
        self.with_context(careos_transition=True).write(vals)
        self._careos_after_transition(action)
        return True

    def _careos_after_transition(self, action):
        """Hook for dependent modules (queue, clinical) to react inside the
        same transaction as the transition."""

    def action_confirm(self):
        return self._careos_transition("confirm")

    def action_check_in(self):
        return self._careos_transition("check_in")

    def action_start(self):
        return self._careos_transition("start")

    def action_complete(self):
        return self._careos_transition("complete")

    def action_no_show(self):
        return self._careos_transition("no_show")

    def action_cancel(self, reason=None):
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Give a reason for the cancellation."))
        return self._careos_transition("cancel", {"cancel_reason": reason})

    def _careos_available_actions(self):
        """Actions the current user can take right now (drives the UI; each
        action re-validates on the server)."""
        self.ensure_one()
        can_write = self.has_access("write")
        actions = [
            action for action in TRANSITIONS
            if can_write and self._careos_role_allows(action) and not self._careos_action_blocker(action)
        ]
        if can_write and self.state in EDITABLE_STATES and self._careos_role_allows("edit"):
            actions.append("reschedule")
        return actions

    # ------------------------------------------------------------------
    # Booking API (used by the booking dialog)
    # ------------------------------------------------------------------

    @api.model
    def careos_book(self, vals, confirm=True):
        """Create an appointment and, by default, confirm it — one transaction."""
        if not self._careos_role_allows("edit"):
            raise AccessError(_("Your role does not allow you to book appointments."))
        allowed = {"patient_id", "provider_id", "type_id", "branch_id", "room_id", "start", "duration", "reason", "notes"}
        appointment = self.create({k: v for k, v in vals.items() if k in allowed})
        if confirm:
            appointment.action_confirm()
        return appointment._careos_payload()

    def careos_reschedule(self, vals):
        self.ensure_one()
        if not self._careos_role_allows("edit"):
            raise AccessError(_("Your role does not allow you to reschedule appointments."))
        allowed = {"provider_id", "type_id", "room_id", "start", "duration", "reason", "notes"}
        self.write({k: v for k, v in vals.items() if k in allowed})
        return self._careos_payload()

    @api.model
    def careos_booking_options(self, branch_id=None):
        """Providers, rooms and visit types bookable at a branch."""
        branch = self.env["careos.branch"].browse(branch_id) if branch_id else self.env.user.careos_branch_id
        providers = self.env["careos.provider"].search([("branch_ids", "in", branch.ids)])
        return {
            "branch": {"id": branch.id, "name": branch.name} if branch else False,
            "providers": [
                {"id": p.id, "name": p.name, "specialty": p.specialty or "", "default_room_id": p.default_room_id.id or False}
                for p in providers
            ],
            "rooms": [{"id": r.id, "name": r.name} for r in self.env["careos.room"].search([("branch_id", "=", branch.id)])],
            "types": [{"id": t.id, "name": t.name, "duration": t.duration} for t in self.env["careos.appointment.type"].search([])],
        }

    @api.model
    def careos_provider_day(self, provider_id, day, exclude_id=None):
        """Busy intervals of a provider on a branch-local day, for the booking
        dialog. Uses sudo so all bookings count, but only returns times."""
        provider = self.env["careos.provider"].browse(provider_id)
        provider.check_access("read")
        branch = self.env.user.careos_branch_id or provider.branch_ids[:1]
        day_start, day_end = branch._careos_day_bounds(date.fromisoformat(day))
        busy = self.sudo().search([
            ("provider_id", "=", provider.id), ("state", "in", BLOCKING_STATES),
            ("start", "<", day_end), ("stop", ">", day_start), ("id", "!=", exclude_id or 0),
        ])
        return [{"start": fields.Datetime.to_string(a.start), "stop": fields.Datetime.to_string(a.stop)} for a in busy]

    # ------------------------------------------------------------------
    # Screen payloads
    # ------------------------------------------------------------------

    def _careos_payload(self):
        self.ensure_one()
        to_str = fields.Datetime.to_string
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": dict(STATES)[self.state],
            "start": to_str(self.start),
            "stop": to_str(self.stop),
            "duration": self.duration,
            "patient": {"id": self.patient_id.id, "name": self.patient_id.name, "ref": self.patient_id.ref},
            "provider": self.provider_id._careos_ref(),
            "type": {"id": self.type_id.id, "name": self.type_id.name},
            "room": {"id": self.room_id.id, "name": self.room_id.name} if self.room_id else False,
            "branch": {"id": self.branch_id.id, "name": self.branch_id.name},
            "reason": self.reason or "",
            "notes": self.notes or "",
            "cancel_reason": self.cancel_reason or "",
            "created_on": to_str(self.create_date),
            "confirmed_at": self.confirmed_at and to_str(self.confirmed_at),
            "checked_in_at": self.checked_in_at and to_str(self.checked_in_at),
            "started_at": self.started_at and to_str(self.started_at),
            "completed_at": self.completed_at and to_str(self.completed_at),
            "cancelled_at": self.cancelled_at and to_str(self.cancelled_at),
            "no_show_at": self.no_show_at and to_str(self.no_show_at),
            "actions": self._careos_available_actions(),
        }

    def careos_get_detail(self):
        self.ensure_one()
        self.check_access("read")
        payload = self._careos_payload()
        payload["history"] = self._careos_history()
        return payload

    def _careos_history(self):
        """Lifecycle events of this appointment, oldest first. Extended by the
        queue module (patient called)."""
        self.ensure_one()
        to_str = fields.Datetime.to_string
        entries = [("created", self.create_date, _("Appointment booked"), self.create_uid.name, "info")]
        labels = [
            ("confirmed_at", _("Appointment confirmed"), "info"),
            ("checked_in_at", _("Patient checked in"), "warning"),
            ("started_at", _("Consultation started"), "info"),
            ("completed_at", _("Visit completed"), "success"),
            ("cancelled_at", _("Appointment cancelled"), "danger"),
            ("no_show_at", _("Marked as no-show"), "neutral"),
        ]
        for field_name, title, tone in labels:
            if self[field_name]:
                detail = self.cancel_reason if field_name == "cancelled_at" else ""
                entries.append((field_name, self[field_name], title, detail, tone))
        events = [
            {"key": f"appt-{self.id}-{key}", "date": to_str(when), "rank": HISTORY_RANK[key],
             "title": title, "detail": detail or "", "tone": tone}
            for key, when, title, detail, tone in entries
        ]
        events.sort(key=lambda e: (e["date"], e["rank"]))
        return events

    def _careos_summary(self):
        """One-line description used in timelines and search results."""
        self.ensure_one()
        local = pytz.utc.localize(self.start).astimezone(self.branch_id._careos_tz())
        return f"{local.strftime('%b %d, %H:%M')} · {self.type_id.name} · {self.provider_id.name}"

    @api.model
    def careos_list(self, filters=None, offset=0, limit=50):
        """Appointment list for the Appointments workspace. Filters: day
        (ISO date, branch-local), state, provider_id, query, scope
        ("branch" = current branch, "all" = every allowed branch)."""
        filters = filters or {}
        domain = Domain.TRUE
        branch = self.env.user.careos_branch_id
        if filters.get("scope", "branch") == "branch" and branch:
            domain &= Domain("branch_id", "=", branch.id)
        if filters.get("day"):
            day_branch = branch or self.env["careos.branch"].search([], limit=1)
            day_start, day_end = day_branch._careos_day_bounds(date.fromisoformat(filters["day"]))
            domain &= Domain("start", ">=", day_start) & Domain("start", "<", day_end)
        if filters.get("state"):
            domain &= Domain("state", "=", filters["state"])
        if filters.get("provider_id"):
            domain &= Domain("provider_id", "=", filters["provider_id"])
        if (filters.get("query") or "").strip():
            domain &= Domain("display_name", "ilike", filters["query"].strip())
        records = self.search(domain, offset=offset, limit=limit, order="start, id")
        return {
            "records": [a._careos_payload() for a in records],
            "total": self.search_count(domain),
        }

    # ------------------------------------------------------------------
    # Reception dashboard
    # ------------------------------------------------------------------

    @api.model
    def careos_reception_dashboard(self):
        """Today at the user's current branch, from live records. Extended by
        the queue module with queue metrics."""
        self.check_access("read")
        branch = self.env.user.careos_branch_id
        if not branch:
            raise UserError(_("Select a branch to see its dashboard."))
        day_start, day_end = branch._careos_day_bounds()
        today = self.search([("branch_id", "=", branch.id), ("start", ">=", day_start), ("start", "<", day_end)])
        counts = {state: 0 for state, _label in STATES}
        for appointment in today:
            counts[appointment.state] += 1
        booked = len(today) - counts["cancelled"]
        arrived = len(today.filtered("checked_in_at"))
        return {
            "date": fields.Date.to_string(branch._careos_today()),
            "branch": {"id": branch.id, "name": branch.name},
            "kpis": [
                {"key": "booked", "label": _("Today's appointments"), "value": booked, "sequence": 10},
                {"key": "arrived", "label": _("Checked in"), "value": arrived, "sequence": 20},
                {"key": "in_progress", "label": _("In consultation"), "value": counts["in_progress"], "sequence": 40},
                {"key": "done", "label": _("Completed"), "value": counts["done"], "sequence": 50},
                {"key": "no_show", "label": _("No-shows"), "value": counts["no_show"], "sequence": 60, "tone": "danger" if counts["no_show"] else ""},
            ],
            "appointments": [a._careos_payload() for a in today.filtered(lambda a: a.state != "cancelled")],
            "upcoming": [
                a._careos_payload() for a in today.filtered(
                    lambda a: a.state == "confirmed" and a.start >= fields.Datetime.now()
                )[:5]
            ],
        }

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _careos_search_result(self):
        self.ensure_one()
        return {
            "id": self.id,
            "title": f"{self.name} · {self.patient_id.name}",
            "detail": f"{self._careos_summary()} · {dict(STATES)[self.state]}",
        }
