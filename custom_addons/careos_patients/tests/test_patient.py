from datetime import date

from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import CareosPatientCase


@tagged("post_install", "-at_install", "careos")
class TestPatient(CareosPatientCase):
    def test_reference_assigned_from_sequence(self):
        other = self.env["careos.patient"].create({"name": "Second Patient"})
        self.assertTrue(self.patient.ref.startswith("P-"))
        self.assertNotEqual(self.patient.ref, other.ref)
        self.assertEqual(other.display_name, f"Second Patient ({other.ref})")

    def test_age_computed_from_date_of_birth(self):
        dob = date.today() - relativedelta(years=30, days=1)
        patient = self.env["careos.patient"].create({"name": "Aged Patient", "date_of_birth": dob})
        self.assertEqual(patient.age, 30)
        patient.date_of_birth = False
        self.assertEqual(patient.age, 0)

    def test_input_is_cleaned(self):
        patient = self.env["careos.patient"].create({"name": "  Nour   El  Din ", "phone": " +20 (100) 555-0199 "})
        self.assertEqual(patient.name, "Nour El Din")
        self.assertEqual(patient.phone_normalized, "201005550199")

    def test_date_of_birth_validation(self):
        Patient = self.env["careos.patient"]
        with self.assertRaises(ValidationError):
            Patient.create({"name": "Future", "date_of_birth": date.today() + relativedelta(days=1)})
        with self.assertRaises(ValidationError):
            Patient.create({"name": "Ancient", "date_of_birth": "1850-01-01"})

    def test_phone_and_email_validation(self):
        Patient = self.env["careos.patient"]
        with self.assertRaises(ValidationError):
            Patient.create({"name": "Bad Phone", "phone": "12-34"})
        with self.assertRaises(ValidationError):
            Patient.create({"name": "Bad Email", "email": "not-an-email"})

    def test_national_id_unique(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["careos.patient"].create({"name": "Impostor", "national_id": "28408190100011"})

    def test_blank_national_ids_do_not_collide(self):
        patients = self.env["careos.patient"].create([{"name": "A", "national_id": " "}, {"name": "B", "national_id": ""}])
        self.assertEqual(patients.mapped("national_id"), [False, False])

    def test_home_branch_must_match_company(self):
        other_company = self.env["res.company"].create({"name": "Other Clinic Group"})
        foreign_branch = self.env["careos.branch"].create(
            {"name": "Foreign", "code": "FRN", "company_id": other_company.id}
        )
        with self.assertRaises(ValidationError):
            self.env["careos.patient"].create({"name": "Mismatch", "branch_id": foreign_branch.id})

    def test_find_duplicates(self):
        Patient = self.env["careos.patient"]
        by_phone = Patient.careos_find_duplicates(name="Someone Else", phone="+20 (100) 555-0101")
        self.assertEqual([d["id"] for d in by_phone], self.patient.ids)
        by_name = Patient.careos_find_duplicates(name="  test   PATIENT ")
        self.assertEqual([d["id"] for d in by_name], self.patient.ids)
        by_nid = Patient.careos_find_duplicates(national_id="28408190100011")
        self.assertEqual([d["id"] for d in by_nid], self.patient.ids)
        self.assertEqual(Patient.careos_find_duplicates(name="Test Patient", exclude_id=self.patient.id), [])
        self.assertEqual(Patient.careos_find_duplicates(name="Unrelated Person", phone="+20 122 555 7777"), [])
        self.assertEqual(Patient.careos_find_duplicates(name="Te"), [])

    def test_search_by_reference_and_phone(self):
        Patient = self.env["careos.patient"]
        self.assertIn(self.patient, Patient.search([("display_name", "ilike", self.patient.ref)]))
        self.assertIn(self.patient, Patient.search([("display_name", "ilike", "555 0101")]))
        self.assertNotIn(self.patient, Patient.search([("display_name", "ilike", "555 0999")]))

    def test_condition_code_uppercased(self):
        self.assertEqual(self.condition.code, "I10")

    def test_allergies_sorted_by_severity(self):
        self.env["careos.patient.allergy"].create(
            {"patient_id": self.patient.id, "allergen": "Latex", "severity": "mild"}
        )
        self.assertEqual(self.patient.allergy_ids.mapped("severity"), ["severe", "mild"])

    def test_changes_are_tracked(self):
        self.patient.phone = "+20 100 555 0102"
        self.env.flush_all()
        self.env.cr.precommit.run()  # tracking is finalized at commit time
        tracked = self.patient.message_ids.tracking_value_ids.field_id.mapped("name")
        self.assertIn("phone", tracked)
