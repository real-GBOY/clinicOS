import random
from datetime import datetime, timedelta

import pytz

from odoo import api, models
from odoo.exceptions import ValidationError

# Weights for historic outcomes. Cardiology gets more no-shows so the
# prototype's "operational alert" has something real to find.
OUTCOMES = [("done", 80), ("no_show", 8), ("cancelled", 12)]
CARDIO_NO_SHOW_BOOST = 14


class CareosAnalytics(models.AbstractModel):
    _inherit = "careos.analytics"

    @api.model
    def _careos_demo_history(self, days=56, seed=7):
        """Synthetic visit history for demo databases: past appointments with
        realistic outcomes, queue waits, encounters and paid/partly-paid
        invoices, imported through the superuser history path."""
        env = self.env
        rng = random.Random(seed)
        branch = env.ref("careos_base.branch_cairo")
        tz = branch._careos_tz()
        providers = env["careos.provider"].search([("branch_ids", "in", branch.ids)])
        patients = env["careos.patient"].search([("company_id", "=", branch.company_id.id)])
        types = env["careos.appointment.type"].search([])
        rooms = env["careos.room"].search([("branch_id", "=", branch.id)])
        Appointment = env["careos.appointment"].with_context(careos_import_history=True)
        Billing = env["careos.billing"]
        today = branch._careos_today()
        work_days = branch._careos_work_days()
        diagnoses = [("I10", "Essential hypertension"), ("E11", "Type 2 diabetes mellitus"), ("J06.9", "Upper respiratory infection"),
                     ("R51", "Headache"), ("E78.5", "Hyperlipidaemia"), ("L20.9", "Atopic dermatitis")]

        for offset in range(days, 0, -1):
            day = today - timedelta(days=offset)
            if day.weekday() not in work_days:
                continue
            for provider in providers:
                slots = rng.sample(range(9 * 2, 16 * 2), rng.randint(2, 4))
                for slot in sorted(slots):
                    local = tz.localize(datetime.combine(day, datetime.min.time()) + timedelta(minutes=slot * 30))
                    start = local.astimezone(pytz.utc).replace(tzinfo=None)
                    patient = rng.choice(patients)
                    visit_type = rng.choice(types)
                    try:
                        with env.cr.savepoint():
                            appointment = Appointment.create({
                                "patient_id": patient.id, "provider_id": provider.id, "type_id": visit_type.id,
                                "branch_id": branch.id, "room_id": provider.default_room_id.id or (rooms[:1].id),
                                "start": start,
                            })
                    except ValidationError:  # patient double-booked in the random draw: skip the slot
                        continue
                    weights = [w + (CARDIO_NO_SHOW_BOOST if s == "no_show" and provider.specialty == "Cardiology" else 0)
                               for s, w in OUTCOMES]
                    outcome = rng.choices([s for s, _w in OUTCOMES], weights)[0]
                    self._careos_demo_play(appointment, outcome, rng, diagnoses, Billing)

    @api.model
    def _careos_demo_play(self, appointment, outcome, rng, diagnoses, Billing):
        """Write a historic visit's lifecycle with plausible timestamps."""
        start = appointment.start
        write = appointment.with_context(careos_transition=True).write
        confirmed = start - timedelta(days=rng.randint(1, 10))
        if outcome == "cancelled":
            write({"state": "cancelled", "confirmed_at": confirmed, "cancelled_at": start - timedelta(hours=rng.randint(2, 30)),
                   "cancel_reason": rng.choice(["Patient request", "Rebooked at another time", "Provider unavailable"])})
            return
        if outcome == "no_show":
            write({"state": "no_show", "confirmed_at": confirmed, "no_show_at": start + timedelta(minutes=30)})
            return
        checked_in = start - timedelta(minutes=rng.randint(0, 15))
        started = checked_in + timedelta(minutes=rng.randint(4, 35))
        completed = started + timedelta(minutes=appointment.duration)
        write({"state": "done", "confirmed_at": confirmed, "checked_in_at": checked_in, "started_at": started,
               "completed_at": completed})
        branch = appointment.branch_id
        self.env["careos.queue.ticket"].with_context(careos_queue_internal=True).create({
            "appointment_id": appointment.id, "queue_date": branch._careos_local_date(start),
            "number": 1000 + appointment.id, "checked_in_at": checked_in, "state": "done",
            "called_at": started, "started_at": started, "completed_at": completed, "room_id": appointment.room_id.id,
        })
        code, description = rng.choice(diagnoses)
        encounter = self.env["careos.encounter"].create({
            "appointment_id": appointment.id, "state": "done", "started_at": started, "completed_at": completed,
            "completed_by_id": appointment.provider_id.user_id.id, "chief_complaint": "Routine review",
            "bp_systolic": rng.randint(110, 150), "bp_diastolic": rng.randint(70, 95), "heart_rate": rng.randint(60, 95),
        })
        self.env["careos.diagnosis"].create({"encounter_id": encounter.id, "code": code, "description": description,
                                             "is_primary": True})
        move_id = Billing.careos_create_invoice(appointment.id)
        move = self.env["account.move"].browse(move_id)
        move.write({"invoice_date": branch._careos_local_date(completed)})
        move.action_post()
        paid = rng.random()
        if paid < 0.85:
            Billing.careos_register_payment(move_id, move.amount_residual, rng.choice(["cash", "card"]))
        elif paid < 0.95:
            Billing.careos_register_payment(move_id, round(move.amount_residual / 2), "cash")
