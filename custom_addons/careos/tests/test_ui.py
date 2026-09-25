from odoo import fields
from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install", "careos")
class TestCareosUi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        branch = env["careos.branch"].create({"name": "Tour Clinic", "code": "TCL", "timezone": "UTC"})
        vals = {"careos_branch_ids": [(6, 0, branch.ids)], "careos_branch_id": branch.id}
        cls.doctor = new_test_user(env, login="tour_doc", groups="careos_base.group_careos_doctor", **vals)
        cls.provider = env["careos.provider"].create({"name": "Dr. Tour", "user_id": cls.doctor.id, "branch_ids": [(6, 0, branch.ids)]})
        warehouse = env["stock.warehouse"].create({"name": "Tour store", "code": "TCL"})
        branch.warehouse_id = warehouse
        env["product.product"].create({"name": "Paracetamol 500mg (20 tabs)", "type": "consu", "is_storable": True,
                                       "careos_item_type": "medication", "careos_strength": "500mg"})
        cls.patient = env["careos.patient"].create({"name": "Farah Tourvisit", "branch_id": branch.id,
                                                    "email": "farah.tour@example.com"})
        appointment = env["careos.appointment"].create({
            "patient_id": cls.patient.id, "provider_id": cls.provider.id, "branch_id": branch.id,
            "type_id": env.ref("careos_appointments.type_consultation").id,
            "start": fields.Datetime.now().replace(second=0, microsecond=0),
        })
        appointment.action_confirm()
        appointment.action_check_in()
        appointment.action_start()
        cls.appointment = appointment
        cls.portal_user = new_test_user(env, login="tour_patient", groups="base.group_portal",
                                        partner_id=cls.patient._careos_partner().id)
        cls.patient.portal_user_id = cls.portal_user

    def test_doctor_visit(self):
        action = self.env.ref("careos_base.action_careos_app")
        self.start_tour(f"/odoo/action-{action.id}", "careos_doctor_visit", login="tour_doc", timeout=180)
        encounter = self.appointment.encounter_ids
        self.assertEqual((encounter.state, self.appointment.state), ("done", "done"))
        self.assertEqual((encounter.bp_systolic, encounter.bp_diastolic), (128, 82))
        self.assertEqual(encounter.chief_complaint, "Headache for three days")
        self.assertEqual(encounter.diagnosis_ids.code, "G44.2")
        self.assertEqual(encounter.prescription_ids.state, "issued")
        self.assertEqual(encounter.lab_order_ids.test_ids.name, "CBC")

    def test_patient_portal(self):
        self.start_tour("/careos/portal", "careos_patient_portal", login="tour_patient", timeout=120)
        messages = self.patient._careos_patient_messages()
        self.assertIn("Can I get my results by e-mail?", messages[-1].body)
        request = self.env["careos.appointment"].search([("patient_id", "=", self.patient.id), ("state", "=", "draft")])
        self.assertEqual(len(request), 1)
