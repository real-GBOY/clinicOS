from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install", "careos")
class TestStaffUi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        branch = cls.env["careos.branch"].create({"name": "Tour HQ", "code": "THQ"})
        new_test_user(cls.env, login="tour_admin", groups="careos_base.group_careos_admin",
                      careos_branch_ids=[(6, 0, branch.ids)], careos_branch_id=branch.id)
        cls.branch = branch

    def test_admin_manages_staff(self):
        action = self.env.ref("careos_base.action_careos_app")
        self.start_tour(f"/odoo/action-{action.id}", "careos_staff_admin", login="tour_admin", timeout=120)
        member = self.env["res.users"].with_context(active_test=False).search([("login", "=", "omar.tourdesk@example.com")])
        self.assertEqual(len(member), 1)
        self.assertFalse(member.active)
        self.assertEqual(set(member._careos_role_keys()), {"reception", "nurse"})
        self.assertEqual(member.careos_branch_ids, self.branch)  # the only branch was preselected
