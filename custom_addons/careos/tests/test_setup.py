from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "careos")
class TestSetupGuide(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.branch = cls.env["careos.branch"].create({"name": "Setup Branch", "code": "SET"})
        vals = {"careos_branch_ids": [(6, 0, cls.branch.ids)], "careos_branch_id": cls.branch.id}
        cls.admin = new_test_user(cls.env, login="s_admin", groups="careos_base.group_careos_admin", **vals)
        cls.reception = new_test_user(cls.env, login="s_reception", groups="careos_base.group_careos_reception", **vals)

    def save(self, step, values):
        return self.env["careos.setup"].with_user(self.admin).careos_setup_save(step, values)

    def test_steps_write_real_configuration(self):
        state = self.save("branch", {"name": "Giza Branch", "code": "giz", "timezone": "Africa/Cairo"})
        self.assertEqual((self.branch.name, self.branch.code, self.branch.timezone), ("Giza Branch", "GIZ", "Africa/Cairo"))
        state = self.save("departments", {"names": ["Cardiology", " Dental ", ""]})
        self.assertEqual(sorted(state["departments"]), ["Cardiology", "Dental"])
        state = self.save("providers", {"providers": [{"name": "Dr. New", "specialty": "Dental", "email": "dr.new@example.com"}]})
        provider = self.env["careos.provider"].search([("name", "=", "Dr. New")])
        self.assertTrue(provider.user_id.has_group("careos_base.group_careos_doctor"))
        self.save("hours", {"days": [6, 0, 1], "start": 8.5, "end": 16})
        self.assertEqual((self.branch.work_days, self.branch.work_start), ("0,1,6", 8.5))
        state = self.save("types", {"types": [{"name": "Dental check-up", "duration": 40}]})
        dental = self.env["careos.appointment.type"].search([("name", "=", "Dental check-up")])
        self.assertEqual(dental.duration, 40)
        self.save("prices", {"types": [{"id": dental.id, "price": 350}], "tests": []})
        self.assertEqual(dental.price, 350)
        self.save("staff", {"invites": [{"name": "Nour Desk", "email": "nour.desk@example.com", "role": "reception"}]})
        staff = self.env["res.users"].search([("login", "=", "nour.desk@example.com")])
        self.assertTrue(staff.has_group("careos_base.group_careos_reception"))
        self.assertEqual(staff.careos_branch_id, self.branch)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.save("hours", {"days": [], "start": 9, "end": 17})
        with self.assertRaises(ValidationError):
            self.save("hours", {"days": [0], "start": 18, "end": 9})
        with self.assertRaises(ValidationError):
            self.save("organization", {"name": " "})

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_admin_only(self):
        with self.assertRaises(AccessError):
            self.env["careos.setup"].with_user(self.reception).careos_setup_state()
