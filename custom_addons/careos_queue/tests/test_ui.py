from odoo import fields
from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install", "careos")
class TestReceptionDayUi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # UTC branch: "today" at the branch is the server's UTC date, whatever
        # the machine's timezone.
        branch = cls.env["careos.branch"].create({"name": "Tour Branch", "code": "TRB", "timezone": "UTC"})
        cls.reception = new_test_user(
            cls.env, login="tour_desk", groups="careos_base.group_careos_reception",
            careos_branch_ids=[(6, 0, branch.ids)], careos_branch_id=branch.id,
        )
        room = cls.env["careos.room"].create({"name": "Room 7", "branch_id": branch.id})
        provider = cls.env["careos.provider"].create(
            {"name": "Dr. Tour Provider", "branch_ids": [(6, 0, branch.ids)], "default_room_id": room.id}
        )
        cls.patient = cls.env["careos.patient"].create({"name": "Nadia Tourtest", "branch_id": branch.id})
        cls.appointment = cls.env["careos.appointment"].create({
            "patient_id": cls.patient.id,
            "provider_id": provider.id,
            "type_id": cls.env.ref("careos_appointments.type_follow_up").id,
            "branch_id": branch.id,
            "start": fields.Datetime.now().replace(second=0, microsecond=0),
        })
        cls.appointment.action_confirm()

    def test_reception_runs_a_visit(self):
        action = self.env.ref("careos_base.action_careos_app")
        self.start_tour(f"/odoo/action-{action.id}", "careos_reception_day", login="tour_desk", timeout=180)
        self.appointment.invalidate_recordset()
        ticket = self.appointment.queue_ticket_ids
        self.assertEqual(self.appointment.state, "done")
        self.assertEqual(ticket.state, "done")
        self.assertEqual(ticket.called_by_id, self.reception)
        self.assertEqual(ticket.room_id.name, "Room 7")
        self.assertTrue(self.appointment.checked_in_at <= self.appointment.started_at <= self.appointment.completed_at)
