import re
from datetime import date

from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import html2plaintext

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PHONE_DIGITS = 7
MAX_TIMELINE_TEXT = 160


def normalize_phone(phone):
    """Digits only, used for duplicate detection and phone search."""
    return re.sub(r"\D", "", phone or "")


class CareosPatient(models.Model):
    """The patient record — CareOS's single source of truth for a person.

    Identity and administrative data live here and are visible to all staff;
    clinical data (conditions, blood type) is restricted to clinical roles at
    the field and model level. Patients belong to the organization (company)
    and can be seen at any branch; ``branch_id`` is the home branch used for
    defaults and reporting.
    """

    _name = "careos.patient"
    _description = "Patient"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, id"
    _rec_names_search = ["name", "ref", "phone", "national_id"]

    ref = fields.Char(
        string="Patient ID", required=True, readonly=True, copy=False, index=True, default=lambda self: _("New")
    )
    name = fields.Char(string="Full name", required=True, index="trigram", tracking=True)
    date_of_birth = fields.Date(tracking=True)
    age = fields.Integer(compute="_compute_age", help="Age in whole years, computed from the date of birth.")
    sex = fields.Selection(
        [("female", "Female"), ("male", "Male"), ("other", "Other")], tracking=True
    )
    phone = fields.Char(tracking=True)
    phone_normalized = fields.Char(compute="_compute_phone_normalized", store=True, index=True)
    email = fields.Char(tracking=True)
    national_id = fields.Char(string="National ID", copy=False, tracking=True)
    street = fields.Char(tracking=True)
    city = fields.Char(tracking=True)
    country_id = fields.Many2one("res.country", tracking=True)

    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    branch_id = fields.Many2one(
        "careos.branch",
        string="Home branch",
        index=True,
        tracking=True,
        default=lambda self: self.env.user.careos_branch_id,
        domain="[('company_id', '=', company_id)]",
    )

    insurance_provider = fields.Char(tracking=True)
    insurance_policy_number = fields.Char(tracking=True)

    contact_ids = fields.One2many("careos.patient.contact", "patient_id", string="Contacts")
    allergy_ids = fields.One2many("careos.patient.allergy", "patient_id", string="Allergies")
    condition_ids = fields.One2many(
        "careos.patient.condition", "patient_id", string="Conditions", groups="careos_base.group_careos_clinical"
    )
    blood_type = fields.Selection(
        [(t, t) for t in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")],
        groups="careos_base.group_careos_clinical",
    )

    active = fields.Boolean(default=True, tracking=True)

    _ref_company_uniq = models.Constraint(
        "UNIQUE(ref, company_id)", "Patient IDs must be unique within the organization."
    )
    _national_id_company_uniq = models.Constraint(
        "UNIQUE(national_id, company_id)", "Another patient is already registered with this national ID."
    )

    # ------------------------------------------------------------------
    # Computes and constraints
    # ------------------------------------------------------------------

    @api.depends("date_of_birth")
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for patient in self:
            dob = patient.date_of_birth
            patient.age = relativedelta(today, dob).years if dob else 0

    @api.depends("phone")
    def _compute_phone_normalized(self):
        for patient in self:
            patient.phone_normalized = normalize_phone(patient.phone) or False

    @api.constrains("date_of_birth")
    def _check_date_of_birth(self):
        today = fields.Date.context_today(self)
        for patient in self:
            dob = patient.date_of_birth
            if dob and dob > today:
                raise ValidationError(_("Date of birth cannot be in the future."))
            if dob and dob < date(1900, 1, 1):
                raise ValidationError(_("Date of birth must be after 1900."))

    @api.constrains("phone")
    def _check_phone(self):
        for patient in self:
            if patient.phone and len(normalize_phone(patient.phone)) < MIN_PHONE_DIGITS:
                raise ValidationError(_("Enter a valid phone number."))

    @api.constrains("email")
    def _check_email(self):
        for patient in self:
            if patient.email and not EMAIL_RE.match(patient.email):
                raise ValidationError(_("Enter a valid email address."))

    @api.constrains("branch_id", "company_id")
    def _check_branch_company(self):
        for patient in self:
            if patient.branch_id and patient.branch_id.company_id != patient.company_id:
                raise ValidationError(_("The home branch must belong to the patient's organization."))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._clean_vals(vals)
            if not vals.get("ref") or vals["ref"] == _("New"):
                vals["ref"] = self.env["ir.sequence"].next_by_code("careos.patient") or _("New")
        # The timeline records registration itself; skip mail's generic "created" log.
        patients = super(CareosPatient, self.with_context(mail_create_nolog=True)).create(vals_list)
        return patients.with_env(self.env)

    def write(self, vals):
        self._clean_vals(vals)
        return super().write(vals)

    @api.model
    def _clean_vals(self, vals):
        for key in ("name", "phone", "email", "national_id"):
            if isinstance(vals.get(key), str):
                vals[key] = vals[key].strip() or False
        if vals.get("name"):
            vals["name"] = re.sub(r"\s+", " ", vals["name"])

    def _compute_display_name(self):
        for patient in self:
            patient.display_name = f"{patient.name} ({patient.ref})" if patient.ref else patient.name

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        digits = normalize_phone(value) if isinstance(value, str) else ""
        if operator in ("ilike", "like") and len(digits) >= 4:
            domain = Domain.OR([domain, Domain("phone_normalized", "like", digits)])
        return domain

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    @api.model
    def careos_find_duplicates(self, name=None, phone=None, national_id=None, exclude_id=None, limit=5):
        """Likely duplicates for a registration in progress. Runs with the
        caller's rights. Matches exact national ID, same phone, or same name."""
        clauses = []
        if national_id and national_id.strip():
            clauses.append([("national_id", "=", national_id.strip())])
        digits = normalize_phone(phone)
        if len(digits) >= MIN_PHONE_DIGITS:
            clauses.append([("phone_normalized", "=", digits)])
        if name and len(name.strip()) >= 3:
            clauses.append([("name", "=ilike", re.sub(r"\s+", " ", name.strip()))])
        if not clauses:
            return []
        domain = ["|"] * (len(clauses) - 1) + [leaf for clause in clauses for leaf in clause]
        if exclude_id:
            domain = ["&", ("id", "!=", exclude_id)] + domain
        return [
            {
                "id": p.id,
                "ref": p.ref,
                "name": p.name,
                "phone": p.phone or "",
                "date_of_birth": p.date_of_birth and fields.Date.to_string(p.date_of_birth),
            }
            for p in self.search(domain, limit=limit)
        ]

    # ------------------------------------------------------------------
    # Patient 360
    # ------------------------------------------------------------------

    def _careos_clinical_access(self):
        return self.env.user.has_group("careos_base.group_careos_clinical")

    def careos_get_profile(self):
        """One payload for the Patient 360 header and overview. Sections the
        user cannot access are omitted, not blanked."""
        self.ensure_one()
        self.check_access("read")
        clinical = self._careos_clinical_access()
        profile = {
            "id": self.id,
            "ref": self.ref,
            "name": self.name,
            "age": self.age if self.date_of_birth else None,
            "date_of_birth": self.date_of_birth and fields.Date.to_string(self.date_of_birth),
            "sex": self.sex or False,
            "sex_label": dict(self._fields["sex"].selection).get(self.sex, ""),
            "phone": self.phone or "",
            "email": self.email or "",
            "national_id": self.national_id or "",
            "address": ", ".join(filter(None, [self.street, self.city, self.country_id.name])),
            "street": self.street or "",
            "city": self.city or "",
            "country_id": self.country_id.id or False,
            "branch": {"id": self.branch_id.id, "name": self.branch_id.name} if self.branch_id else False,
            "insurance_provider": self.insurance_provider or "",
            "insurance_policy_number": self.insurance_policy_number or "",
            "active": self.active,
            "registered_on": fields.Datetime.to_string(self.create_date),
            "contacts": [c._careos_payload() for c in self.contact_ids],
            "allergies": [a._careos_payload() for a in self.allergy_ids.filtered("active")],
            "can_edit": self.has_access("write"),
            "can_edit_clinical": clinical and self.env["careos.patient.allergy"].has_access("create"),
            "can_upload": self.has_access("write"),
            "clinical_access": clinical,
            "document_count": self.env["ir.attachment"].search_count(
                [("res_model", "=", self._name), ("res_id", "=", self.id)]
            ),
        }
        if clinical:
            profile["blood_type"] = self.blood_type or False
            profile["conditions"] = [c._careos_payload() for c in self.condition_ids.filtered("active")]
        profile["timeline"] = self._careos_timeline_events()
        return profile

    def _careos_timeline_events(self, limit=30):
        """Chronological events for the Patient 360 timeline, newest first.
        Domain modules extend this to add encounters, prescriptions, lab
        orders or invoices. Each event: date (datetime string), kind, title,
        detail, tone."""
        self.ensure_one()
        events = [{
            "key": f"registered-{self.id}",
            "date": fields.Datetime.to_string(self.create_date),
            "kind": "registration",
            "title": _("Patient registered"),
            "detail": _("%(ref)s · by %(user)s", ref=self.ref, user=self.create_uid.name),
            "tone": "success",
        }]
        messages = self.env["mail.message"].search(
            [("model", "=", self._name), ("res_id", "=", self.id), ("message_type", "in", ("comment", "notification"))],
            limit=limit,
            order="date desc, id desc",
        )
        # Tracking values are only readable through sudo; restricted fields are
        # never tracked on this model, so every tracked field is safe to show.
        for message in messages.sudo():
            fields_changed = message.tracking_value_ids.field_id.mapped("field_description")
            text = html2plaintext(message.body or "").strip()
            if len(text) > MAX_TIMELINE_TEXT:
                text = text[:MAX_TIMELINE_TEXT].rstrip() + "…"
            if fields_changed:
                title, detail, tone = _("Record updated"), ", ".join(fields_changed), "neutral"
            elif message.message_type == "comment" and text:
                title, detail, tone = _("Note added"), text, "info"
            elif text:
                title, detail, tone = text, "", "neutral"
            else:
                continue
            events.append({
                "key": f"message-{message.id}",
                "date": fields.Datetime.to_string(message.date),
                "kind": "note" if message.message_type == "comment" else "update",
                "title": title,
                "detail": " · ".join(filter(None, [detail, message.author_id.name])),
                "tone": tone,
            })
        events.sort(key=lambda e: e["date"], reverse=True)
        return events[:limit]

    def careos_get_documents(self):
        self.ensure_one()
        self.check_access("read")
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", self._name), ("res_id", "=", self.id)], order="create_date desc"
        )
        return [
            {
                "id": a.id,
                "name": a.name,
                "mimetype": a.mimetype or "",
                "size": a.file_size,
                "uploaded_on": fields.Datetime.to_string(a.create_date),
                "uploaded_by": a.create_uid.name,
            }
            for a in attachments
        ]

    def careos_attach_document(self, name, datas):
        """Upload a document to the patient's record (base64 ``datas``)."""
        self.ensure_one()
        self.check_access("write")
        attachment = self.env["ir.attachment"].create({
            "name": name,
            "datas": datas,
            "res_model": self._name,
            "res_id": self.id,
        })
        self.message_post(body=_("Document uploaded: %s", attachment.name), message_type="notification")
        return attachment.id

    def careos_get_messages(self, limit=50):
        self.ensure_one()
        self.check_access("read")
        messages = self.env["mail.message"].search(
            [("model", "=", self._name), ("res_id", "=", self.id), ("message_type", "=", "comment")],
            limit=limit,
            order="date desc, id desc",
        )
        return [
            {
                "id": m.id,
                "body": m.body,
                "author": m.author_id.name or "",
                "date": fields.Datetime.to_string(m.date),
            }
            for m in messages
        ]

    def careos_post_note(self, text):
        """Log an internal note. Plain text only: it is escaped server-side."""
        self.ensure_one()
        self.check_access("write")
        text = (text or "").strip()
        if not text:
            raise ValidationError(_("A note cannot be empty."))
        body = Markup("<br/>").join(escape(line) for line in text.splitlines())
        message = self.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note")
        return message.id

    # ------------------------------------------------------------------
    # Global search
    # ------------------------------------------------------------------

    def _careos_search_result(self):
        self.ensure_one()
        details = [
            self.ref,
            f"{self.age}y" if self.date_of_birth else "",
            self.phone or "",
        ]
        return {"id": self.id, "title": self.name, "detail": " · ".join(filter(None, details))}
