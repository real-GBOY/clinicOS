from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CareosAppointmentType(models.Model):
    """A bookable visit type (New patient, Follow-up…) with its default length.
    Pricing is attached by the finance module, not here."""

    _name = "careos.appointment.type"
    _description = "Appointment Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    duration = fields.Integer(string="Duration (minutes)", required=True, default=30)

    @api.constrains("duration")
    def _check_duration(self):
        for appointment_type in self:
            if not 5 <= appointment_type.duration <= 480:
                raise ValidationError(_("A visit must last between 5 minutes and 8 hours."))
