from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.careos_base.models.authorization import has_role, require_role

STATES = [
    ("waiting", "Waiting"),
    ("called", "Called"),
    ("in_consultation", "In Consultation"),
    ("done", "Completed"),
    ("no_show", "No-show"),
]

# Queue lifecycle from the CareOS specification (§6):
#   Waiting → Called → In Consultation → Completed · Waiting → No-show
# A called patient who never comes to the room can also become a no-show
# (documented in docs/domain-model.md). Only "call" is a queue-only action;
# start, complete and no-show are appointment transitions that the queue
# mirrors, so the two records can never disagree.
QUEUE_TRANSITIONS = {
    "call": {"waiting"},
    "start": {"waiting", "called"},
    "complete": {"in_consultation"},
    "no_show": {"waiting", "called"},
}
CALL_ROLES = ("reception", "nurse", "doctor")
OPEN_STATES = ("waiting", "called", "in_consultation")


class CareosQueueTicket(models.Model):
    """A patient's place in the branch queue for one visit. Created by
    checking in an appointment — never by hand."""

    _name = "careos.queue.ticket"
    _description = "Queue Ticket"
    _order = "queue_date desc, checked_in_at, id"

    appointment_id = fields.Many2one("careos.appointment", required=True, index=True, ondelete="restrict", readonly=True)
    patient_id = fields.Many2one(related="appointment_id.patient_id", store=True, index=True)
    provider_id = fields.Many2one(related="appointment_id.provider_id", store=True, index=True)
    branch_id = fields.Many2one(related="appointment_id.branch_id", store=True, index=True)
    company_id = fields.Many2one(related="appointment_id.company_id", store=True, index=True)
    queue_date = fields.Date(required=True, index=True, readonly=True, help="Branch-local day of the queue.")
    number = fields.Integer(required=True, readonly=True, help="Ticket number, restarting daily per branch.")
    state = fields.Selection(STATES, required=True, default="waiting", index=True)
    room_id = fields.Many2one("careos.room", readonly=True)

    checked_in_at = fields.Datetime(required=True, readonly=True)
    called_at = fields.Datetime(readonly=True)
    called_by_id = fields.Many2one("res.users", readonly=True)
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    no_show_at = fields.Datetime(readonly=True)

    _appointment_uniq = models.Constraint("UNIQUE(appointment_id)", "An appointment has at most one queue ticket.")
    _number_uniq = models.Constraint("UNIQUE(branch_id, queue_date, number)", "Ticket numbers are unique per branch and day.")
    _branch_day_idx = models.Index("(branch_id, queue_date, state)")

    def _compute_display_name(self):
        for ticket in self:
            ticket.display_name = f"#{ticket.number:03d} · {ticket.patient_id.name}"

    # ------------------------------------------------------------------
    # Creation (from check-in only)
    # ------------------------------------------------------------------

    @api.model
    def _careos_create_for(self, appointment):
        """Issue the next ticket number for the appointment's branch today.
        The branch row is locked so two simultaneous check-ins cannot draw
        the same number."""
        branch = appointment.branch_id
        self.env.cr.execute("SELECT id FROM careos_branch WHERE id = %s FOR UPDATE", [branch.id])
        queue_date = branch._careos_today()
        # ORM search (flushes pending tickets); sudo so tickets the user cannot
        # see still count.
        last = self.sudo().search(
            [("branch_id", "=", branch.id), ("queue_date", "=", queue_date)], order="number desc", limit=1,
        )
        number = last.number + 1
        return self.with_context(careos_queue_internal=True).create({
            "appointment_id": appointment.id,
            "queue_date": queue_date,
            "number": number,
            "checked_in_at": appointment.checked_in_at,
            "room_id": appointment.room_id.id,
        })

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("careos_queue_internal"):
            raise UserError(_("Queue tickets are created by checking in an appointment."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("careos_queue_internal"):
            raise UserError(_("The queue changes only through its workflow actions."))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _careos_check_source(self, action):
        for ticket in self:
            if ticket.state not in QUEUE_TRANSITIONS[action]:
                raise UserError(_("Ticket #%(number)03d is %(state)s.",
                                  number=ticket.number, state=dict(STATES)[ticket.state]))

    def action_call(self):
        """Call the next patient to a room (queue-only transition)."""
        require_role(self.env, CALL_ROLES, _("Your role does not allow you to call patients."))
        self.check_access("write")
        self._careos_check_source("call")
        for ticket in self:
            room = ticket.appointment_id.room_id or ticket.provider_id.default_room_id
            ticket.with_context(careos_queue_internal=True).write({
                "state": "called",
                "called_at": fields.Datetime.now(),
                "called_by_id": self.env.uid,
                "room_id": room.id,
            })
        return True

    def action_start(self):
        """Start the consultation. This is an appointment transition; the
        ticket follows through the appointment hook."""
        self._careos_check_source("start")
        return self.appointment_id.action_start()

    def action_complete(self):
        self._careos_check_source("complete")
        return self.appointment_id.action_complete()

    def action_no_show(self):
        self._careos_check_source("no_show")
        return self.appointment_id.action_no_show()

    def _careos_sync(self, action):
        """Mirror an appointment transition (called from the appointment,
        inside its transaction)."""
        now = fields.Datetime.now()
        for ticket in self:
            if action == "start":
                vals = {"state": "in_consultation", "started_at": now}
                if not ticket.called_at:
                    # Doctor took the patient straight from the waiting area.
                    vals.update(called_at=now, called_by_id=self.env.uid)
            elif action == "complete":
                vals = {"state": "done", "completed_at": now}
            elif action == "no_show":
                vals = {"state": "no_show", "no_show_at": now}
            else:
                continue
            ticket.with_context(careos_queue_internal=True).write(vals)

    def _careos_available_actions(self):
        self.ensure_one()
        appointment_actions = self.appointment_id._careos_available_actions()
        actions = []
        if self.state == "waiting" and has_role(self.env, CALL_ROLES) and self.has_access("write"):
            actions.append("call")
        # The board offers "start" once the patient has been called; starting
        # straight from waiting stays possible from the appointment itself.
        if self.state == "called" and "start" in appointment_actions:
            actions.append("start")
        for action in ("complete", "no_show"):
            if self.state in QUEUE_TRANSITIONS[action] and action in appointment_actions:
                actions.append(action)
        return actions

    # ------------------------------------------------------------------
    # Payloads
    # ------------------------------------------------------------------

    def _careos_payload(self, position=None):
        self.ensure_one()
        to_str = fields.Datetime.to_string
        appointment = self.appointment_id
        return {
            "id": self.id,
            "number": self.number,
            "label": f"#{self.number:03d}",
            "state": self.state,
            "state_label": dict(STATES)[self.state],
            "position": position,
            "patient": {"id": self.patient_id.id, "name": self.patient_id.name, "ref": self.patient_id.ref},
            "provider": {"id": self.provider_id.id, "name": self.provider_id.name},
            "appointment": {
                "id": appointment.id,
                "name": appointment.name,
                "start": to_str(appointment.start),
                "type": appointment.type_id.name,
            },
            "room": {"id": self.room_id.id, "name": self.room_id.name} if self.room_id else False,
            "checked_in_at": to_str(self.checked_in_at),
            "called_at": self.called_at and to_str(self.called_at),
            "started_at": self.started_at and to_str(self.started_at),
            "completed_at": self.completed_at and to_str(self.completed_at),
            "actions": self._careos_available_actions(),
        }

    @api.model
    def careos_queue_board(self):
        """Today's queue at the user's current branch."""
        self.check_access("read")
        branch = self.env.user.careos_branch_id
        if not branch:
            raise UserError(_("Select a branch to see its queue."))
        tickets = self.search([("branch_id", "=", branch.id), ("queue_date", "=", branch._careos_today())])
        waiting = tickets.filtered(lambda t: t.state in ("waiting", "called")).sorted(
            lambda t: (t.state != "called", t.checked_in_at, t.id)
        )
        return {
            "branch": {"id": branch.id, "name": branch.name},
            "now": fields.Datetime.to_string(fields.Datetime.now()),
            "waiting": [t._careos_payload(position=i + 1) for i, t in enumerate(waiting)],
            "in_consultation": [t._careos_payload() for t in tickets.filtered(lambda t: t.state == "in_consultation")],
            "done": [t._careos_payload() for t in tickets.filtered(lambda t: t.state == "done").sorted("completed_at", reverse=True)],
            "no_show_count": len(tickets.filtered(lambda t: t.state == "no_show")),
        }
