from odoo.tests import new_test_user

from odoo.addons.careos_prescriptions.tests.test_prescriptions import CareosPharmacyCase


class CareosBillingCase(CareosPharmacyCase):
    """A completed visit ready to bill (consultation, lab test, dispensed medicine)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.finance_user = new_test_user(
            cls.env, login="f_finance", groups="careos_base.group_careos_finance",
            careos_branch_ids=[(6, 0, cls.branch_a.ids)], careos_branch_id=cls.branch_a.id,
        )
        cls.type_follow_up.price = 450
        cls.env.ref("careos_laboratory.test_glucose").price = 80

    def completed_visit(self):
        """Consultation + lab test + dispensed medicine, visit closed."""
        appointment, encounter = self.visit()
        encounter.with_user(self.doctor).careos_order_lab(self.env.ref("careos_laboratory.test_glucose").ids)
        rx = self.prescribe(encounter)
        rx.with_user(self.doctor).action_issue()
        rx.with_user(self.pharmacist).action_dispense()
        self.diagnose(encounter)
        encounter.with_user(self.doctor).action_complete()
        return appointment
