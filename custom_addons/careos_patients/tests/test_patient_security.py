from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import CareosPatientCase


@tagged("post_install", "-at_install", "careos")
class TestPatientSecurity(CareosPatientCase):
    """Server-side enforcement of the spec's permission matrix (§9) for the
    Patients module. The UI hides actions too, but these are the real gates."""

    def test_every_role_can_read_patients(self):
        for user in (self.reception, self.doctor, self.nurse, self.lab, self.finance, self.careos_admin):
            with self.subTest(user=user.login):
                patient = self.patient.with_user(user)
                self.assertEqual(patient.name, "Test Patient")
                self.assertEqual(patient.allergy_ids.allergen, "Penicillin")

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_non_careos_user_has_no_access(self):
        with self.assertRaises(AccessError):
            self.patient.with_user(self.outsider).read(["name"])
        with self.assertRaises(AccessError):
            self.env["careos.patient"].with_user(self.outsider).search([])

    def test_reception_and_doctor_register_and_edit(self):
        for user in (self.reception, self.doctor):
            with self.subTest(user=user.login):
                Patient = self.env["careos.patient"].with_user(user)
                patient = Patient.create({"name": f"Registered by {user.login}"})
                patient.write({"phone": "+20 100 555 0300"})
                self.assertTrue(patient.ref.startswith("P-"))

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_read_only_roles_cannot_register_or_edit(self):
        for user in (self.nurse, self.lab, self.finance, self.careos_admin):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.env["careos.patient"].with_user(user).create({"name": "Not allowed"})
                with self.assertRaises(AccessError):
                    self.patient.with_user(user).write({"phone": "+20 100 555 0400"})

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_nobody_deletes_patients(self):
        for user in (self.reception, self.doctor, self.careos_admin):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.patient.with_user(user).unlink()

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_conditions_are_clinical_only(self):
        for user in (self.doctor, self.nurse):
            with self.subTest(user=user.login):
                self.assertEqual(self.patient.with_user(user).condition_ids, self.condition.with_user(user))
        for user in (self.reception, self.lab, self.finance, self.careos_admin):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.condition.with_user(user).read(["name"])
                with self.assertRaises(AccessError):
                    self.patient.with_user(user).read(["condition_ids"])
                with self.assertRaises(AccessError):
                    self.patient.with_user(user).read(["blood_type"])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_only_clinical_roles_record_allergies(self):
        for user in (self.doctor, self.nurse):
            with self.subTest(user=user.login):
                allergy = self.env["careos.patient.allergy"].with_user(user).create(
                    {"patient_id": self.patient.id, "allergen": f"Latex ({user.login})"}
                )
                allergy.active = False  # entries are retired, not deleted
                with self.assertRaises(AccessError):
                    allergy.unlink()
        for user in (self.reception, self.lab):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.env["careos.patient.allergy"].with_user(user).create(
                        {"patient_id": self.patient.id, "allergen": "Latex"}
                    )

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_contacts_managed_by_front_desk_and_doctors(self):
        contact = self.env["careos.patient.contact"].with_user(self.reception).create(
            {"patient_id": self.patient.id, "name": "Next Of Kin", "phone": "+20 100 555 0500"}
        )
        self.assertEqual(contact.with_user(self.lab).name, "Next Of Kin")
        with self.assertRaises(AccessError):
            contact.with_user(self.nurse).write({"phone": "+20 100 555 0501"})

    def test_other_company_patients_are_invisible(self):
        other_company = self.env["res.company"].create({"name": "Other Clinic Group"})
        foreign = self.env["careos.patient"].create({"name": "Foreign Patient", "company_id": other_company.id})
        visible = self.env["careos.patient"].with_user(self.reception).search([("name", "like", "Patient")])
        self.assertIn(self.patient, visible)
        self.assertNotIn(foreign, visible)

    def test_global_search_respects_access(self):
        Search = self.env["careos.search"]
        results = Search.with_user(self.lab).careos_global_search("Test Pat")
        self.assertEqual([(r["model"], r["id"]) for r in results], [("careos.patient", self.patient.id)])
        self.assertEqual(results[0]["screen"], "patient")
        # A user without patient access gets nothing rather than an error.
        self.assertEqual(Search.with_user(self.outsider).careos_global_search("Test Pat"), [])
