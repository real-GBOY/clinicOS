from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "careos")
class TestCareosBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Branch = cls.env["careos.branch"]
        cls.branch_a = Branch.create({"name": "North", "code": " nth "})
        cls.branch_b = Branch.create({"name": "South", "code": "STH"})
        cls.branch_other = Branch.create({"name": "Elsewhere", "code": "ELS"})
        cls.reception = new_test_user(
            cls.env,
            login="t_reception",
            groups="careos_base.group_careos_reception",
            careos_branch_ids=[(6, 0, (cls.branch_a | cls.branch_b).ids)],
            careos_branch_id=cls.branch_a.id,
        )
        cls.doctor = new_test_user(cls.env, login="t_doctor", groups="careos_base.group_careos_doctor")
        cls.outsider = new_test_user(cls.env, login="t_outsider", groups="base.group_user")

    def test_branch_code_normalized_and_unique(self):
        self.assertEqual(self.branch_a.code, "NTH")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["careos.branch"].create({"name": "Duplicate", "code": "nth"})

    def test_department_unique_per_branch(self):
        Dept = self.env["careos.department"]
        Dept.create({"name": "Cardiology", "branch_id": self.branch_a.id})
        Dept.create({"name": "Cardiology", "branch_id": self.branch_b.id})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            Dept.create({"name": "Cardiology", "branch_id": self.branch_a.id})

    def test_current_branch_must_be_allowed(self):
        with self.assertRaises(ValidationError):
            self.reception.careos_branch_id = self.branch_other

    def test_role_groups_imply_staff(self):
        self.assertTrue(self.reception.has_group("careos_base.group_careos_user"))
        self.assertFalse(self.reception.has_group("careos_base.group_careos_clinical"))
        self.assertTrue(self.doctor.has_group("careos_base.group_careos_clinical"))

    def test_session_context(self):
        ctx = self.env["res.users"].with_user(self.reception).careos_get_session_context()
        self.assertEqual(ctx["roles"], ["reception"])
        self.assertEqual(ctx["branch"]["id"], self.branch_a.id)
        self.assertEqual({b["id"] for b in ctx["branches"]}, {self.branch_a.id, self.branch_b.id})
        self.assertFalse(ctx["is_system"])

    def test_session_context_requires_careos_role(self):
        with self.assertRaises(AccessError):
            self.env["res.users"].with_user(self.outsider).careos_get_session_context()

    def test_switch_branch(self):
        Users = self.env["res.users"].with_user(self.reception)
        result = Users.careos_switch_branch(self.branch_b.id)
        self.assertEqual(result["id"], self.branch_b.id)
        self.assertEqual(self.reception.careos_branch_id, self.branch_b)
        with self.assertRaises(AccessError):
            Users.careos_switch_branch(self.branch_other.id)

    def test_staff_cannot_edit_branches(self):
        with self.assertRaises(AccessError):
            self.branch_a.with_user(self.reception).write({"name": "Renamed"})

    def test_global_search_ignores_short_queries(self):
        self.assertEqual(self.env["careos.search"].with_user(self.reception).careos_global_search("a"), [])
