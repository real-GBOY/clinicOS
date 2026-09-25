from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "careos")
class TestNotifications(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        branch = cls.env["careos.branch"].create({"name": "Notify Branch", "code": "NTF"})
        vals = {"careos_branch_ids": [(6, 0, branch.ids)], "careos_branch_id": branch.id}
        cls.branch = branch
        cls.alice = new_test_user(cls.env, login="n_alice", groups="careos_base.group_careos_reception", **vals)
        cls.bob = new_test_user(cls.env, login="n_bob", groups="careos_base.group_careos_reception")

    def test_own_notifications_only(self):
        Notification = self.env["careos.notification"]
        Notification._careos_notify(self.alice | self.bob, "Hello", kind="info")
        mine = Notification.with_user(self.alice).search([])
        self.assertEqual(mine.user_id, self.alice)
        inbox = Notification.with_user(self.alice).careos_inbox()
        self.assertEqual((inbox["unread"], inbox["items"][0]["title"]), (1, "Hello"))
        Notification.with_user(self.alice).careos_mark_all_read()
        self.assertEqual(Notification.with_user(self.alice).careos_inbox()["unread"], 0)
        self.assertEqual(Notification.with_user(self.bob).careos_inbox()["unread"], 1)

    def test_dedupe_and_role_targeting(self):
        Notification = self.env["careos.notification"]
        users = Notification._careos_users_with_roles(["reception"], self.branch)
        self.assertIn(self.alice, users)
        self.assertNotIn(self.bob, users)  # not assigned to the branch
        Notification._careos_notify(users, "Low stock", dedupe_key="k1")
        Notification._careos_notify(users, "Low stock", dedupe_key="k1")
        self.assertEqual(Notification.with_user(self.alice).careos_inbox()["unread"], 1)
