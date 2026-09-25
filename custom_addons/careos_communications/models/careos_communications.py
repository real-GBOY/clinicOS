from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html2plaintext

INBOX_ROLES = {"reception", "doctor", "nurse", "manager", "admin"}
REMINDER_LEAD = timedelta(hours=24)


class CareosPatient(models.Model):
    _inherit = "careos.patient"

    def _careos_patient_messages(self, limit=50):
        """Patient-facing conversation (not internal notes), oldest first."""
        subtype = self.env.ref("careos_communications.mt_patient_message")
        return self.env["mail.message"].sudo().search([
            ("model", "=", "careos.patient"), ("res_id", "in", self.ids), ("subtype_id", "=", subtype.id),
        ], order="date desc, id desc", limit=limit).sorted(lambda m: (m.date, m.id))

    def _careos_message_payload(self, message):
        from_patient = bool(message.author_id) and message.author_id == self.sudo().partner_id and bool(self.sudo().partner_id)
        return {
            "id": message.id,
            "text": html2plaintext(message.body or "").strip(),
            "author": message.author_id.name or "",
            "from_patient": from_patient,
            "date": fields.Datetime.to_string(message.date),
        }

    def careos_get_profile(self):
        profile = super().careos_get_profile()
        roles = set(self.env.user._careos_role_keys())
        profile["messages_access"] = self.env.su or bool(INBOX_ROLES & roles)
        return profile

    def careos_get_conversation(self):
        self.ensure_one()
        self.check_access("read")
        self.env["careos.communications"]._careos_require_inbox()
        return [self._careos_message_payload(m) for m in self._careos_patient_messages()]

    def careos_send_message(self, text):
        """Staff reply to the patient. The message is stored on the patient
        record and delivered by e-mail when the patient has an address."""
        self.ensure_one()
        self.check_access("read")
        self.env["careos.communications"]._careos_require_inbox()
        text = (text or "").strip()
        if not text:
            raise ValidationError(_("A message cannot be empty."))
        body = Markup("<br/>").join(escape(line) for line in text.splitlines())
        partner = self._careos_partner()
        self.sudo().message_post(
            body=body, message_type="comment", subtype_xmlid="careos_communications.mt_patient_message",
            partner_ids=partner.ids if partner and partner.email else [],
        )
        return self.careos_get_conversation()

    def _careos_post_from_patient(self, text):
        """Message written by the patient (portal)."""
        self.ensure_one()
        text = (text or "").strip()
        if not text:
            raise ValidationError(_("A message cannot be empty."))
        partner = self._careos_partner()
        body = Markup("<br/>").join(escape(line) for line in text.splitlines())
        self.sudo().message_post(body=body, message_type="comment", author_id=partner.id,
                                 subtype_xmlid="careos_communications.mt_patient_message")
        Notification = self.env["careos.notification"]
        Notification._careos_notify(
            Notification._careos_users_with_roles(["reception"], self.branch_id),
            _("New message — %s", self.name), body=text[:120], kind="info", screen="inbox", res_id=self.id,
        )


class CareosReminder(models.Model):
    """An appointment reminder to the patient, sent through a delivery
    provider. Providers are pluggable (``_careos_send_<channel>``); e-mail is
    built in, SMS/WhatsApp providers are added by integration modules."""

    _name = "careos.reminder"
    _description = "Appointment Reminder"
    _order = "scheduled_at, id"

    appointment_id = fields.Many2one("careos.appointment", required=True, index=True, ondelete="cascade")
    patient_id = fields.Many2one(related="appointment_id.patient_id", store=True, index=True)
    branch_id = fields.Many2one(related="appointment_id.branch_id", store=True, index=True)
    company_id = fields.Many2one(related="appointment_id.company_id", store=True, index=True)
    channel = fields.Selection([("email", "E-mail"), ("sms", "SMS")], required=True, default="email")
    scheduled_at = fields.Datetime(required=True, index=True)
    state = fields.Selection([("scheduled", "Scheduled"), ("sent", "Sent"), ("failed", "Failed"), ("cancelled", "Cancelled")],
                             required=True, default="scheduled", index=True)
    sent_at = fields.Datetime(readonly=True)
    error = fields.Char(readonly=True)

    def _careos_text(self):
        self.ensure_one()
        appointment = self.appointment_id
        return _("Reminder: your %(type)s appointment with %(provider)s is on %(when)s at %(branch)s.",
                 type=appointment.type_id.name.lower(), provider=appointment.provider_id.name,
                 when=appointment._careos_summary().split(" · ")[0], branch=appointment.branch_id.name)

    def _careos_send_email(self):
        email = self.patient_id.email
        if not email:
            raise UserError(_("The patient has no e-mail address."))
        self.env["mail.mail"].sudo().create({
            "subject": _("Appointment reminder"),
            "email_to": email,
            "body_html": Markup("<p>%s</p>") % self._careos_text(),
            "auto_delete": True,
        }).send()

    def _careos_send_sms(self):
        raise UserError(_("No SMS provider is configured."))

    def _careos_deliver(self):
        for reminder in self:
            if reminder.appointment_id.state not in ("draft", "confirmed"):
                reminder.state = "cancelled"
                continue
            try:
                getattr(reminder, f"_careos_send_{reminder.channel}")()
            except UserError as error:
                reminder.write({"state": "failed", "error": str(error)})
            else:
                reminder.write({"state": "sent", "sent_at": fields.Datetime.now(), "error": False})
                reminder.patient_id.sudo().message_post(
                    body=reminder._careos_text(), message_type="notification",
                    subtype_xmlid="careos_communications.mt_patient_message",
                )

    @api.model
    def _careos_cron_send(self):
        self.search([("state", "=", "scheduled"), ("scheduled_at", "<=", fields.Datetime.now())])._careos_deliver()

    def _careos_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "patient": {"id": self.patient_id.id, "name": self.patient_id.name},
            "text": self._careos_text(),
            "channel": dict(self._fields["channel"].selection)[self.channel],
            "scheduled_at": fields.Datetime.to_string(self.scheduled_at),
            "state": self.state,
            "state_label": dict(self._fields["state"].selection)[self.state],
            "error": self.error or "",
        }


class CareosAppointment(models.Model):
    _inherit = "careos.appointment"

    reminder_ids = fields.One2many("careos.reminder", "appointment_id")

    def _careos_after_transition(self, action):
        super()._careos_after_transition(action)
        if action == "confirm":
            self._careos_schedule_reminders()
        elif action in ("cancel", "no_show", "check_in"):
            self.sudo().reminder_ids.filtered(lambda r: r.state == "scheduled").write({"state": "cancelled"})

    def careos_reschedule(self, vals):
        result = super().careos_reschedule(vals)
        if "start" in vals:
            self.sudo().reminder_ids.filtered(lambda r: r.state == "scheduled").write({"state": "cancelled"})
            self._careos_schedule_reminders()
            doctor = self.provider_id.user_id
            if doctor:
                self.env["careos.notification"]._careos_notify(
                    doctor, _("Appointment rescheduled — %s", self.patient_id.name), body=self._careos_summary(),
                    kind="info", screen="appointment", res_id=self.id)
        return result

    def _careos_schedule_reminders(self):
        now = fields.Datetime.now()
        for appointment in self.sudo():
            when = max(appointment.start - REMINDER_LEAD, now)
            if appointment.start > now:
                channel = "email" if appointment.patient_id.email else "sms"
                self.env["careos.reminder"].sudo().create({
                    "appointment_id": appointment.id, "scheduled_at": when, "channel": channel,
                })


class CareosCommunications(models.AbstractModel):
    """Communication Center (prototype "Inbox")."""

    _name = "careos.communications"
    _description = "CareOS Communication Center"

    @api.model
    def _careos_require_inbox(self):
        if not self.env.su and not INBOX_ROLES & set(self.env.user._careos_role_keys()):
            raise AccessError(_("Your role does not have access to patient communication."))

    @api.model
    def careos_inbox(self):
        """Conversations at the user's branch (latest first) and upcoming reminders."""
        self._careos_require_inbox()
        branch = self.env.user.careos_branch_id
        subtype = self.env.ref("careos_communications.mt_patient_message")
        messages = self.env["mail.message"].sudo().search([
            ("model", "=", "careos.patient"), ("subtype_id", "=", subtype.id), ("message_type", "=", "comment"),
        ], order="date desc, id desc", limit=300)
        patients = self.env["careos.patient"].browse(list(dict.fromkeys(messages.mapped("res_id"))))
        patients = patients.filtered(lambda p: p.has_access("read") and (not branch or p.branch_id == branch))
        conversations = []
        for patient in patients[:30]:
            last = messages.filtered(lambda m: m.res_id == patient.id)[:1]
            payload = patient._careos_message_payload(last)
            conversations.append({
                "patient": {"id": patient.id, "name": patient.name, "ref": patient.ref},
                "preview": payload["text"][:90],
                "date": payload["date"],
                "needs_reply": payload["from_patient"],
            })
        domain = [("state", "in", ("scheduled", "failed"))]
        if branch:
            domain.append(("branch_id", "=", branch.id))
        reminders = self.env["careos.reminder"].sudo().search(domain, limit=15)
        return {
            "conversations": conversations,
            "reminders": [r._careos_payload() for r in reminders],
        }

    @api.model
    def careos_retry_reminder(self, reminder_id):
        self._careos_require_inbox()
        reminder = self.env["careos.reminder"].sudo().browse(reminder_id)
        reminder.appointment_id.check_access("read")
        reminder._careos_deliver()
        return reminder._careos_payload()
