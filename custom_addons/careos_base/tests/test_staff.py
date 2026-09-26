from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "careos")
class TestStaff(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Branch = cls.env["careos.branch"]
        cls.north = Branch.create({"name": "Staff North", "code": "SNO"})
        cls.south = Branch.create({"name": "Staff South", "code": "SSO"})
        cls.cardio = cls.env["careos.department"].create({"name": "Cardiology", "branch_id": cls.north.id})
        both = {"careos_branch_ids": [(6, 0, (cls.north | cls.south).ids)], "careos_branch_id": cls.north.id}
        cls.admin = new_test_user(cls.env, login="s_admin", groups="careos_base.group_careos_admin", **both)
        cls.manager = new_test_user(cls.env, login="s_manager", groups="careos_base.group_careos_manager",
                                    careos_branch_ids=[(6, 0, cls.north.ids)], careos_branch_id=cls.north.id)
        cls.reception = new_test_user(cls.env, login="s_reception", groups="careos_base.group_careos_reception",
                                      careos_branch_ids=[(6, 0, cls.south.ids)], careos_branch_id=cls.south.id)

    def staff(self, user=None):
        return self.env["careos.staff"].with_user(user or self.admin)

    def invite(self, **values):
        payload = {"name": "Salma Testnurse", "email": "salma.nurse@example.com", "roles": ["nurse"],
                   "branch_ids": [self.north.id], "department_id": self.cardio.id}
        payload.update(values)
        return self.staff().careos_staff_invite(payload)

    def test_invite_creates_account_with_access(self):
        detail = self.invite()
        user = self.env["res.users"].browse(detail["id"])
        self.assertEqual(detail["status"], "invited")
        self.assertEqual(user.login, "salma.nurse@example.com")
        self.assertTrue(user.has_group("careos_base.group_careos_nurse"))
        self.assertTrue(user.has_group("careos_base.group_careos_clinical"))  # implied by the role
        self.assertFalse(user.has_group("careos_base.group_careos_doctor"))
        self.assertEqual((user.careos_branch_ids, user.careos_branch_id, user.careos_department_id),
                         (self.north, self.north, self.cardio))
        self.assertEqual(user.action_id.id, self.env.ref("careos_base.action_careos_app").id)
        self.assertIn("Invited as Nurse", detail["history"][0]["summary"])
        self.assertEqual(detail["history"][0]["actor"], self.admin.name)

    def test_invite_validation(self):
        self.invite()
        cases = [
            {"email": "salma.nurse@example.com"},           # already exists
            {"email": "SALMA.NURSE@example.com"},           # case-insensitive
            {"email": "not-an-email"},
            {"name": "  "},
            {"roles": []},
            {"roles": ["surgeon"]},
            {"branch_ids": []},
            {"branch_ids": [self.south.id]},                # Cardiology is a North department
            {"branch_ids": [self.north.id], "branch_id": self.south.id},
        ]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.invite(email=values.pop("email", "other@example.com"), **values)

    def test_save_roles_branches_and_history(self):
        user_id = self.invite()["id"]
        detail = self.staff().careos_staff_save(user_id, {
            "name": "Salma Adel", "email": "salma.nurse@example.com", "roles": ["nurse", "lab"],
            "branch_ids": [self.north.id, self.south.id], "branch_id": self.south.id, "department_id": False,
        })
        user = self.env["res.users"].browse(user_id)
        self.assertEqual(set(detail["roles"]), {"nurse", "lab"})
        self.assertEqual((user.name, user.careos_branch_id, user.careos_department_id),
                         ("Salma Adel", self.south, self.env["careos.department"]))
        summary = detail["history"][0]["summary"]
        for part in ("Roles: Nurse → Nurse, Laboratory", "Branches:", "Department: —", "Details updated"):
            self.assertIn(part, summary)
        # Removing a role removes its access, other groups are untouched.
        user.group_ids = [(4, self.env.ref("base.group_partner_manager").id)]
        self.staff().careos_staff_save(user_id, dict(self.payload(user), roles=["lab"]))
        self.assertFalse(user.has_group("careos_base.group_careos_nurse"))
        self.assertFalse(user.has_group("careos_base.group_careos_clinical"))
        self.assertTrue(user.has_group("base.group_partner_manager"))

    def payload(self, user, **values):
        vals = {"name": user.name, "email": user.login, "roles": user._careos_role_keys(),
                "branch_ids": user.careos_branch_ids.ids, "branch_id": user.careos_branch_id.id,
                "department_id": user.careos_department_id.id}
        vals.update(values)
        return vals

    def test_plain_login_accounts_stay_editable(self):
        # Accounts created outside CareOS may sign in with a plain login.
        plain = new_test_user(self.env, login="deskuser", groups="careos_base.group_careos_reception",
                              careos_branch_ids=[(6, 0, self.north.ids)], careos_branch_id=self.north.id)
        self.staff().careos_staff_save(plain.id, self.payload(plain, roles=["reception", "finance"]))
        self.assertTrue(plain.has_group("careos_base.group_careos_finance"))
        self.assertEqual(plain.login, "deskuser")
        with self.assertRaises(ValidationError):  # a changed sign-in must be an e-mail
            self.staff().careos_staff_save(plain.id, self.payload(plain, email="otherdesk"))

    def test_system_account_is_not_staff(self):
        ids = [r["id"] for r in self.staff().careos_staff_overview(status="")["staff"]]
        self.assertNotIn(self.env.ref("base.user_root").id, ids)
        with self.assertRaises(AccessError):
            self.staff().careos_staff_detail(self.env.ref("base.user_root").id)

    def test_no_change_writes_no_history(self):
        user_id = self.invite()["id"]
        user = self.env["res.users"].browse(user_id)
        detail = self.staff().careos_staff_save(user_id, self.payload(user))
        self.assertEqual(len(detail["history"]), 1)

    def test_admin_self_protection(self):
        with self.assertRaises(ValidationError):
            self.staff().careos_staff_save(self.admin.id, self.payload(self.admin, roles=["manager"]))
        with self.assertRaises(ValidationError):
            self.staff().careos_staff_set_active(self.admin.id, False)
        self.assertTrue(self.admin.has_group("careos_base.group_careos_admin"))

    def test_keeps_one_active_administrator(self):
        system = new_test_user(self.env, login="s_system", groups="base.group_system,careos_base.group_careos_user")
        others = self.env["careos.staff"]._careos_active_admins() - self.admin
        others.write({"active": False})
        with self.assertRaises(ValidationError):
            self.staff(system).careos_staff_save(self.admin.id, self.payload(self.admin, roles=["manager"]))
        with self.assertRaises(ValidationError):
            self.staff(system).careos_staff_set_active(self.admin.id, False)
        self.assertTrue(self.admin.active)

    def test_deactivate_and_reactivate(self):
        user_id = self.invite()["id"]
        detail = self.staff().careos_staff_set_active(user_id, False)
        self.assertEqual(detail["status"], "inactive")
        self.assertFalse(self.env["res.users"].browse(user_id).active)
        overview = self.staff().careos_staff_overview(status="inactive")
        self.assertIn(user_id, [r["id"] for r in overview["staff"]])
        detail = self.staff().careos_staff_set_active(user_id, True)
        self.assertEqual(detail["status"], "invited")
        self.assertEqual([h["summary"] for h in detail["history"][:2]], ["Account reactivated", "Account deactivated"])
        self.staff().careos_staff_set_active(user_id, False)
        with self.assertRaises(ValidationError):  # no invitations to deactivated accounts
            self.staff().careos_staff_resend_invite(user_id)

    def test_overview_filters_and_kpis(self):
        self.invite()
        overview = self.staff().careos_staff_overview(status="invited", role="nurse", query="testnurse")
        self.assertEqual([r["login"] for r in overview["staff"]], ["salma.nurse@example.com"])
        self.assertEqual(self.staff().careos_staff_overview(status="", query="TESTNURSE")["staff"][0]["name"], "Salma Testnurse")
        kpis = {k["key"]: k["value"] for k in overview["kpis"]}
        self.assertGreaterEqual(kpis["invited"], 1)
        self.assertGreaterEqual(kpis["admins"], 1)
        roles = {r["key"]: r for r in overview["roles"]}
        self.assertEqual(set(roles), {"reception", "doctor", "nurse", "lab", "pharmacy", "finance", "manager", "admin"})
        self.assertTrue(overview["can_manage"])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_permissions(self):
        user_id = self.invite()["id"]
        # Managers read staff of their own branches only, and change nothing.
        overview = self.staff(self.manager).careos_staff_overview(status="")
        logins = {r["login"] for r in overview["staff"]}
        self.assertIn("salma.nurse@example.com", logins)
        self.assertNotIn("s_reception", logins)  # South only
        self.assertFalse(overview["can_manage"])
        self.assertEqual([b["id"] for b in overview["branches"]], self.north.ids)
        with self.assertRaises(AccessError):
            self.staff(self.manager).careos_staff_detail(self.reception.id)
        user = self.env["res.users"].browse(user_id)
        for call in (
            lambda s: s.careos_staff_invite({"name": "X", "email": "x@example.com", "roles": ["nurse"], "branch_ids": [self.north.id]}),
            lambda s: s.careos_staff_save(user_id, self.payload(user, roles=["admin"])),
            lambda s: s.careos_staff_set_active(user_id, False),
            lambda s: s.careos_staff_resend_invite(user_id),
        ):
            with self.assertRaises(AccessError):
                call(self.staff(self.manager))
            with self.assertRaises(AccessError):
                call(self.staff(self.reception))
        with self.assertRaises(AccessError):
            self.staff(self.reception).careos_staff_overview()
        # The audit log is not writable, even by administrators.
        with self.assertRaises(AccessError):
            self.env["careos.staff.log"].with_user(self.admin).create(
                {"user_id": user_id, "actor_id": self.admin.id, "summary": "forged"})
        self.assertFalse(self.staff().careos_staff_overview(status="", query="nobody-by-this-name")["staff"])
