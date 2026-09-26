from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.careos_base.models.authorization import has_role, require_role

PREVIEW_ROLES = {"reception", "doctor", "nurse", "manager", "admin"}
INVITE_ROLES = {"reception", "admin"}
NEW_RESULT_DAYS = 14


class CareosPatient(models.Model):
    _inherit = "careos.patient"

    portal_user_id = fields.Many2one("res.users", string="Portal login", readonly=True, copy=False, index=True)

    def careos_get_profile(self):
        profile = super().careos_get_profile()
        profile["portal"] = {
            "active": bool(self.sudo().portal_user_id),
            "can_invite": has_role(self.env, INVITE_ROLES),
        }
        return profile

    def careos_invite_portal(self):
        """Give the patient a portal login (their e-mail) and send the
        invitation to set a password."""
        self.ensure_one()
        require_role(self.env, INVITE_ROLES, _("Only the front desk can invite patients to the portal."))
        self.check_access("write")
        patient = self.sudo()
        if not patient.email:
            raise ValidationError(_("Add the patient's e-mail address first."))
        if patient.portal_user_id:
            raise UserError(_("%s already has portal access.", patient.name))
        partner = patient._careos_partner()
        partner.email = patient.email
        existing = self.env["res.users"].sudo().with_context(active_test=False).search([("login", "=", patient.email)], limit=1)
        if existing:
            raise ValidationError(_("Another account already uses %s.", patient.email))
        user = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
            "login": patient.email,
            "partner_id": partner.id,
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        patient.portal_user_id = user
        try:
            user.action_reset_password()
        except Exception:  # mail server not configured: the account still exists
            pass
        patient.message_post(body=_("Portal access sent to %s.", patient.email), message_type="notification")
        return self.careos_get_profile()


class CareosPortal(models.AbstractModel):
    """Everything a patient sees in the portal, for their own record only.

    Portal users have no model access: every read goes through this service,
    which resolves the patient linked to the logged-in user and reads with
    sudo strictly within that patient's records. Staff preview the same
    payload for a patient they can read ("View as patient")."""

    _name = "careos.portal"
    _description = "CareOS Patient Portal"

    @api.model
    def _careos_current_patient(self):
        patient = self.env["careos.patient"].sudo().search([("portal_user_id", "=", self.env.uid)], limit=1)
        if not patient:
            raise AccessError(_("This account is not linked to a patient record."))
        return patient

    @api.model
    def _careos_payload(self, patient, preview=False):
        patient = patient.sudo()
        to_str = fields.Datetime.to_string
        now = fields.Datetime.now()
        Appointment = self.env["careos.appointment"].sudo()
        appointments = Appointment.search([("patient_id", "=", patient.id)], order="start desc", limit=30)
        upcoming = appointments.filtered(lambda a: a.state in ("draft", "confirmed") and a.start >= now).sorted("start")

        def appt(a):
            return {
                "id": a.id, "start": to_str(a.start), "provider": a.provider_id.name, "type": a.type_id.name,
                "branch": a.branch_id.name, "state": a.state,
                "state_label": _("Requested") if a.state == "draft" else dict(a._fields["state"].selection)[a.state],
                "can_reschedule": a.state == "confirmed" and a.start >= now,
            }

        lines = self.env["careos.prescription.line"].sudo().search(
            [("patient_id", "=", patient.id), ("state", "in", ("issued", "dispensed"))])
        orders = self.env["careos.lab.order"].sudo().search(
            [("patient_id", "=", patient.id), ("state", "in", ("verified", "completed"))], limit=20)
        recent = now - timedelta(days=NEW_RESULT_DAYS)
        invoices = self.env["account.move"].sudo().search([
            ("careos_patient_id", "=", patient.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
        ], order="invoice_date desc", limit=20)
        messages = patient._careos_patient_messages()
        return {
            "preview": preview,
            "patient": {"id": patient.id, "name": patient.name, "first_name": patient.name.split(" ")[0]},
            "next_appointment": appt(upcoming[:1]) if upcoming else False,
            "appointments": [appt(a) for a in appointments.filtered(lambda a: a.state != "cancelled")],
            "prescriptions": [{
                "id": line.id, "med": line.product_id.name.split(" (")[0], "dose": line.dose, "freq": line.frequency,
                "duration": _("%s days", line.duration_days), "instructions": line.instructions or "",
                "state": line.state, "status": dict(line.prescription_id._fields["state"].selection)[line.state],
            } for line in lines],
            "lab_results": [{
                "id": order.id, "tests": ", ".join(order.test_ids.mapped("name")), "doctor": order.provider_id.name,
                "date": to_str(order.verified_at or order.create_date), "state": order.state,
                "status": _("Reviewed") if order.state == "completed" else _("Available"),
                "is_new": bool(order.verified_at and order.verified_at >= recent),
                "results": [r._careos_payload() for r in order.result_ids],
            } for order in orders],
            "invoices": [{
                **move._careos_summary(),
                "pay_url": move.get_portal_url() if move.payment_state in ("not_paid", "partial") else False,
            } for move in invoices],
            "balance_due": sum(invoices.mapped("amount_residual")),
            "currency": patient.company_id.currency_id.symbol,
            "messages": [patient._careos_message_payload(m) for m in messages],
        }

    # ------------------------------------------------------------------
    # Patient (portal) API — called from the portal controller
    # ------------------------------------------------------------------

    @api.model
    def careos_portal_data(self):
        return self._careos_payload(self._careos_current_patient())

    @api.model
    def careos_portal_message(self, text):
        patient = self._careos_current_patient()
        patient._careos_post_from_patient(text)
        return self._careos_payload(patient)

    @api.model
    def careos_portal_reschedule(self, appointment_id, note=""):
        """Ask the clinic to move a confirmed appointment (the front desk
        reschedules it; patients cannot move bookings themselves)."""
        patient = self._careos_current_patient()
        appointment = self.env["careos.appointment"].sudo().browse(appointment_id)
        if appointment.patient_id != patient:
            raise AccessError(_("Appointment not found."))
        text = _("I would like to reschedule my %(type)s appointment on %(when)s.",
                 type=appointment.type_id.name.lower(), when=appointment._careos_summary().split(" · ")[0])
        if (note or "").strip():
            text += " " + note.strip()
        patient._careos_post_from_patient(text)
        return self._careos_payload(patient)

    @api.model
    def careos_portal_booking_options(self, day=None):
        patient = self._careos_current_patient()
        branch = patient.branch_id or self.env["careos.branch"].sudo().search([("company_id", "=", patient.company_id.id)], limit=1)
        Appointment = self.env["careos.appointment"].sudo()
        options = Appointment.careos_booking_options(branch.id)
        day = day or fields.Date.to_string(branch._careos_today() + timedelta(days=1))
        busy = {p["id"]: Appointment.careos_provider_day(p["id"], day) for p in options["providers"]}
        return {"branch": options["branch"], "providers": options["providers"], "types": options["types"],
                "day": day, "busy": busy, "work_start": branch.work_start, "work_end": branch.work_end}

    @api.model
    def careos_portal_book(self, provider_id, type_id, start, reason=""):
        """Request an appointment; it stays a draft until the front desk confirms."""
        patient = self._careos_current_patient()
        branch = patient.branch_id or self.env["careos.branch"].sudo().search([("company_id", "=", patient.company_id.id)], limit=1)
        # Arguments come from the browser: accept only a doctor and visit type
        # the portal actually offers at the patient's branch.
        options = self.env["careos.appointment"].sudo().careos_booking_options(branch.id)
        if int(provider_id or 0) not in {p["id"] for p in options["providers"]} \
                or int(type_id or 0) not in {t["id"] for t in options["types"]}:
            raise ValidationError(_("Choose a doctor and a visit type from the list."))
        try:
            start_dt = fields.Datetime.to_datetime(start)
        except (TypeError, ValueError):
            start_dt = None
        if not start_dt or start_dt <= fields.Datetime.now():
            raise ValidationError(_("Choose a time in the future."))
        appointment = self.env["careos.appointment"].sudo().create({
            "patient_id": patient.id, "provider_id": int(provider_id), "type_id": int(type_id), "branch_id": branch.id,
            "start": start_dt, "reason": (reason or "").strip()[:500] or _("Requested online"),
        })
        Notification = self.env["careos.notification"]
        Notification._careos_notify(
            Notification._careos_users_with_roles(["reception"], branch),
            _("Appointment request — %s", patient.name), body=appointment._careos_summary(),
            kind="info", screen="appointment", res_id=appointment.id)
        return self._careos_payload(patient)

    # ------------------------------------------------------------------
    # Staff preview ("View as patient")
    # ------------------------------------------------------------------

    @api.model
    def careos_preview(self, patient_id):
        require_role(self.env, PREVIEW_ROLES, _("Your role cannot preview the patient portal."))
        patient = self.env["careos.patient"].browse(patient_id)
        patient.check_access("read")
        return self._careos_payload(patient, preview=True)
