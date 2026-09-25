from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install", "careos")
class TestPatientUi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        branch = cls.env["careos.branch"].create({"name": "Tour Branch", "code": "TUR"})
        new_test_user(
            cls.env,
            login="tour_reception",
            groups="careos_base.group_careos_reception",
            careos_branch_ids=[(6, 0, branch.ids)],
            careos_branch_id=branch.id,
        )

    def test_reception_registers_patient(self):
        action = self.env.ref("careos_base.action_careos_app")
        self.start_tour(
            f"/odoo/action-{action.id}", "careos_patient_registration", login="tour_reception", timeout=120
        )
        patient = self.env["careos.patient"].search([("name", "=", "Yasmin Tourtest")])
        self.assertEqual(len(patient), 1)
        self.assertEqual(patient.phone_normalized, "201005559911")
        self.assertEqual(patient.branch_id.code, "TUR")
        self.assertTrue(any("Called to confirm insurance details." in body for body in patient.message_ids.mapped("body")))
