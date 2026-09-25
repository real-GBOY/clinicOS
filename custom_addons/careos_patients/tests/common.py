from odoo.tests import TransactionCase, new_test_user


class CareosPatientCase(TransactionCase):
    """Shared fixture: one branch, one user per CareOS role, one patient."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.branch = cls.env["careos.branch"].create({"name": "Test Branch", "code": "TST"})
        branch_vals = {"careos_branch_ids": [(6, 0, cls.branch.ids)], "careos_branch_id": cls.branch.id}

        def user(login, group):
            return new_test_user(cls.env, login=login, groups=group, **branch_vals)

        cls.reception = user("p_reception", "careos_base.group_careos_reception")
        cls.doctor = user("p_doctor", "careos_base.group_careos_doctor")
        cls.nurse = user("p_nurse", "careos_base.group_careos_nurse")
        cls.lab = user("p_lab", "careos_base.group_careos_lab")
        cls.finance = user("p_finance", "careos_base.group_careos_finance")
        cls.careos_admin = user("p_admin", "careos_base.group_careos_admin")
        cls.outsider = new_test_user(cls.env, login="p_outsider", groups="base.group_user")

        cls.patient = cls.env["careos.patient"].create({
            "name": "Test Patient",
            "date_of_birth": "1984-08-19",
            "sex": "male",
            "phone": "+20 100 555 0101",
            "national_id": "28408190100011",
            "branch_id": cls.branch.id,
        })
        cls.allergy = cls.env["careos.patient.allergy"].create({
            "patient_id": cls.patient.id,
            "allergen": "Penicillin",
            "severity": "severe",
        })
        cls.condition = cls.env["careos.patient.condition"].create({
            "patient_id": cls.patient.id,
            "name": "Essential hypertension",
            "code": "i10",
        })
        # Fixture records are "committed": later edits are tracked as updates
        # rather than folded into creation, as they would be in production.
        cls.env.flush_all()
        cls.env.cr.precommit.run()
