from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install", "careos")
class TestBookingUi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        branch = cls.env["careos.branch"].create({"name": "Booking Branch", "code": "BKB", "timezone": "UTC"})
        new_test_user(
            cls.env, login="tour_booker", groups="careos_base.group_careos_reception",
            careos_branch_ids=[(6, 0, branch.ids)], careos_branch_id=branch.id,
        )
        cls.provider = cls.env["careos.provider"].create({"name": "Dr. Booking", "branch_ids": [(6, 0, branch.ids)]})
        cls.patient = cls.env["careos.patient"].create({"name": "Omar Booktest", "branch_id": branch.id})

    def test_book_from_patient_360(self):
        action = self.env.ref("careos_base.action_careos_app")
        self.start_tour(f"/odoo/action-{action.id}", "careos_book_appointment", login="tour_booker", timeout=120)
        appointment = self.env["careos.appointment"].search([("patient_id", "=", self.patient.id)])
        self.assertEqual(len(appointment), 1)
        self.assertEqual(appointment.state, "confirmed")
        self.assertEqual(appointment.provider_id, self.provider)
        self.assertEqual(appointment.reason, "Blood pressure review")
        self.assertEqual(appointment.duration, 30)  # first visit type: New patient
