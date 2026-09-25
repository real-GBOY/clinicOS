from datetime import datetime, timedelta

from odoo.tests import TransactionCase, new_test_user

# Tests run on a frozen clock (see FROZEN_NOW) with a UTC branch, so "today",
# "past" and "future" are deterministic.
FROZEN_NOW = "2030-03-12 10:00:00"
NOW = datetime(2030, 3, 12, 10, 0)


class CareosAppointmentCase(TransactionCase):
    """Two branches, one user per role, providers, a room, visit types."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Branch = cls.env["careos.branch"]
        cls.branch_a = Branch.create({"name": "Branch A", "code": "BRA", "timezone": "UTC"})
        cls.branch_b = Branch.create({"name": "Branch B", "code": "BRB", "timezone": "UTC"})

        def user(login, group, branches):
            return new_test_user(
                cls.env, login=login, groups=group,
                careos_branch_ids=[(6, 0, branches.ids)], careos_branch_id=branches[:1].id,
            )

        cls.reception = user("a_reception", "careos_base.group_careos_reception", cls.branch_a)
        cls.reception_b = user("a_reception_b", "careos_base.group_careos_reception", cls.branch_b)
        cls.doctor = user("a_doctor", "careos_base.group_careos_doctor", cls.branch_a)
        cls.doctor2 = user("a_doctor2", "careos_base.group_careos_doctor", cls.branch_a)
        cls.nurse = user("a_nurse", "careos_base.group_careos_nurse", cls.branch_a)
        cls.lab = user("a_lab", "careos_base.group_careos_lab", cls.branch_a)
        cls.finance = user("a_finance", "careos_base.group_careos_finance", cls.branch_a)
        cls.manager = user("a_manager", "careos_base.group_careos_manager", cls.branch_a)
        cls.careos_admin = user("a_admin", "careos_base.group_careos_admin", cls.branch_a)

        cls.room_1 = cls.env["careos.room"].create({"name": "Room 1", "branch_id": cls.branch_a.id})
        cls.room_2 = cls.env["careos.room"].create({"name": "Room 2", "branch_id": cls.branch_a.id})
        cls.room_b = cls.env["careos.room"].create({"name": "Room 1", "branch_id": cls.branch_b.id})
        Provider = cls.env["careos.provider"]
        cls.provider = Provider.create({
            "name": "Dr. Test One", "user_id": cls.doctor.id,
            "branch_ids": [(6, 0, (cls.branch_a | cls.branch_b).ids)], "default_room_id": cls.room_1.id,
        })
        cls.provider2 = Provider.create({
            "name": "Dr. Test Two", "user_id": cls.doctor2.id, "branch_ids": [(6, 0, cls.branch_a.ids)],
        })
        cls.provider_b = Provider.create({"name": "Dr. Branch B", "branch_ids": [(6, 0, cls.branch_b.ids)]})
        cls.type_follow_up = cls.env.ref("careos_appointments.type_follow_up")  # 20 min
        cls.type_consult = cls.env.ref("careos_appointments.type_consultation")  # 30 min

        Patient = cls.env["careos.patient"]
        cls.patient = Patient.create({"name": "Appointment Patient", "branch_id": cls.branch_a.id})
        cls.patient2 = Patient.create({"name": "Second Appointment Patient", "branch_id": cls.branch_a.id})

    def book(self, start=None, confirm=True, user=None, **vals):
        """Create an appointment (as ``user`` or superuser)."""
        values = {
            "patient_id": self.patient.id,
            "provider_id": self.provider.id,
            "type_id": self.type_follow_up.id,
            "branch_id": self.branch_a.id,
            "start": start if start is not None else NOW - timedelta(minutes=30),
            **vals,
        }
        Appointment = self.env["careos.appointment"]
        if user:
            Appointment = Appointment.with_user(user)
        appointment = Appointment.create(values)
        if confirm:
            appointment.action_confirm()
        return appointment

    def bring_to(self, appointment, state):
        """Walk an appointment through the real workflow up to ``state``."""
        paths = {
            "draft": [],
            "confirmed": ["confirm"],
            "checked_in": ["confirm", "check_in"],
            "in_progress": ["confirm", "check_in", "start"],
            "done": ["confirm", "check_in", "start", "complete"],
            "cancelled": ["confirm", "cancel"],
            "no_show": ["confirm", "no_show"],
        }
        for action in paths[state]:
            if action == "cancel":
                appointment.action_cancel("Test cancellation")
            else:
                getattr(appointment, f"action_{action}")()
        self.assertEqual(appointment.state, state)
        return appointment
