from datetime import timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW, NOW
from odoo.addons.careos_finance.tests.common import CareosBillingCase


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestAnalytics(CareosBillingCase):
    """Figures on the Manager Workspace must equal what the records say."""

    def test_manager_dashboard_matches_records(self):
        appointment = self.completed_visit()
        Billing = self.env["careos.billing"].with_user(self.reception)
        move_id = Billing.careos_create_invoice(appointment.id)
        Billing.careos_post(move_id)
        Billing.careos_register_payment(move_id, 300, "cash")
        no_show = self.book(start=NOW - timedelta(hours=2), patient_id=self.patient2.id, provider_id=self.provider2.id)
        no_show.action_no_show()

        dashboard = self.env["careos.analytics"].with_user(self.manager).careos_manager_dashboard()
        kpis = {k["key"]: k["value"] for k in dashboard["kpis"]}
        currency = self.branch_a.company_id.currency_id.symbol
        self.assertEqual(kpis["revenue"], f"780 {currency}")
        self.assertEqual(kpis["visits"], "1")
        self.assertEqual(kpis["no_show"], "50.0%")  # 1 no-show out of 2 attended slots
        self.assertEqual(kpis["outstanding"], f"480 {currency}")
        util = {row["name"]: row["value"] for row in dashboard["utilization"]}
        self.assertGreater(util["Dr. Test One"], 0)

    def test_operations_and_finance_tabs(self):
        appointment = self.completed_visit()
        Billing = self.env["careos.billing"].with_user(self.reception)
        Billing.careos_post(Billing.careos_create_invoice(appointment.id))
        Analytics = self.env["careos.analytics"].with_user(self.manager)
        finance = Analytics.careos_analytics("finance")
        by_line = {row["name"]: row["value"] for row in finance["revenue_by_service"]}
        self.assertEqual(by_line, {"Consultations": 450, "Laboratory": 80, "Pharmacy dispensing": 250})
        operations = Analytics.careos_analytics("operations")
        self.assertEqual(len(operations["wait"]), 1)
        patients = Analytics.careos_analytics("patients")
        self.assertEqual(sum(week["new"] for week in patients["patient_growth"]), 1)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_access(self):
        for user in (self.reception, self.doctor, self.lab):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.env["careos.analytics"].with_user(user).careos_manager_dashboard()
