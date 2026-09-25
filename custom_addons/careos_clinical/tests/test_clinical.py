from datetime import timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_appointments.tests.common import FROZEN_NOW, NOW

from .common import CareosVisitCase

ACL_LOGGERS = ("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.models")


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestEncounter(CareosVisitCase):
    def test_check_in_opens_encounter(self):
        appointment, encounter = self.visit(started=False)
        self.assertEqual(len(encounter), 1)
        self.assertEqual(encounter.state, "open")
        self.assertTrue(encounter.name.startswith("ENC-"))
        self.assertEqual((encounter.patient_id, encounter.provider_id), (self.patient, self.provider))
        appointment.with_user(self.doctor).action_start()
        self.assertEqual(encounter.started_at, NOW)

    @mute_logger(*ACL_LOGGERS)
    def test_front_desk_cannot_read_clinical_record(self):
        _appointment, encounter = self.visit()
        for user in (self.reception, self.lab, self.finance, self.manager):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                encounter.with_user(user).read(["notes"])

    @mute_logger(*ACL_LOGGERS)
    def test_nurse_records_vitals_only(self):
        _appointment, encounter = self.visit(started=False)
        encounter.with_user(self.nurse).careos_save({"bp_systolic": 132, "bp_diastolic": 85, "weight": 82, "height": 177})
        self.assertEqual(encounter.vitals_recorded_by_id, self.nurse)
        self.assertEqual(encounter.bmi, 26.2)
        with self.assertRaises(AccessError):
            encounter.with_user(self.nurse).write({"notes": "Not a nurse's note"})
        with self.assertRaises(AccessError):
            self.env["careos.diagnosis"].with_user(self.nurse).create(
                {"encounter_id": encounter.id, "description": "Not a nurse's diagnosis"})

    def test_vitals_plausibility(self):
        _appointment, encounter = self.visit()
        with self.assertRaises(ValidationError):
            encounter.with_user(self.doctor).careos_save({"heart_rate": 400})
        with self.assertRaises(ValidationError):
            encounter.with_user(self.doctor).careos_save({"bp_systolic": 80, "bp_diastolic": 90})

    @mute_logger(*ACL_LOGGERS)
    def test_doctor_sees_own_encounters_only(self):
        _a, mine = self.visit()
        _b, other = self.visit(provider_id=self.provider2.id, patient_id=self.patient2.id)
        self.assertEqual(self.env["careos.encounter"].with_user(self.doctor).search([]), mine)
        with self.assertRaises(AccessError):
            other.with_user(self.doctor).read(["notes"])

    def test_complete_requires_diagnosis_and_closes_visit(self):
        appointment, encounter = self.visit()
        doctor_encounter = encounter.with_user(self.doctor)
        doctor_encounter.careos_save({"chief_complaint": "BP review", "notes": "Stable."})
        with self.assertRaises(UserError):
            doctor_encounter.action_complete()
        self.diagnose(encounter)
        doctor_encounter.action_complete()
        self.assertEqual((encounter.state, appointment.state), ("done", "done"))
        self.assertEqual(encounter.completed_by_id, self.doctor)
        with self.assertRaises(UserError):
            doctor_encounter.careos_save({"notes": "Edited after sign-off"})
        with self.assertRaises(UserError):
            self.diagnose(encounter, "E11", "Diabetes")

    @mute_logger(*ACL_LOGGERS)
    def test_only_doctors_sign_off(self):
        _appointment, encounter = self.visit()
        self.diagnose(encounter)
        with self.assertRaises(AccessError):
            encounter.with_user(self.nurse).action_complete()

    def test_front_desk_close_leaves_encounter_unsigned(self):
        appointment, encounter = self.visit()
        appointment.with_user(self.reception).action_complete()
        self.assertEqual(encounter.state, "open")
        dashboard = self.env["careos.appointment"].with_user(self.doctor).careos_doctor_dashboard()
        self.assertEqual([e["id"] for e in dashboard["unsigned"]], encounter.ids)

    def test_workspace_payload_respects_role(self):
        _appointment, encounter = self.visit()
        doctor_view = encounter.with_user(self.doctor).careos_get_workspace()
        self.assertTrue(doctor_view["can_edit_clinical"])
        self.assertTrue(doctor_view["can_complete"])
        self.assertEqual([a["allergen"] for a in doctor_view["patient_context"]["allergies"]], ["Penicillin"])
        nurse_view = encounter.with_user(self.nurse).careos_get_workspace()
        self.assertFalse(nurse_view["can_edit_clinical"])
        self.assertTrue(nurse_view["can_edit_vitals"])

    def test_follow_ups_until_booked(self):
        _appointment, encounter = self.visit()
        encounter.with_user(self.doctor).careos_save({"follow_up_date": "2030-03-15", "follow_up_reason": "BP check"})
        rows = self.env["careos.encounter"].with_user(self.reception).careos_follow_ups()
        self.assertEqual([(r["patient"]["id"], r["reason"]) for r in rows], [(self.patient.id, "BP check")])
        self.book(start=NOW + timedelta(days=3), provider_id=self.provider2.id)
        self.assertEqual(self.env["careos.encounter"].with_user(self.reception).careos_follow_ups(), [])
        with self.assertRaises(ValidationError):
            encounter.with_user(self.doctor).careos_save({"follow_up_date": "2030-03-01"})

    def test_timeline_and_payload_links(self):
        appointment, encounter = self.visit()
        self.diagnose(encounter)
        encounter.with_user(self.doctor).action_complete()
        timeline = self.patient.with_user(self.doctor).careos_get_profile()["timeline"]
        completed = [e for e in timeline if e["title"] == "Encounter completed"]
        self.assertIn("Essential hypertension (I10)", completed[0]["detail"])
        # The encounter link is exposed to clinicians only.
        self.assertEqual(appointment.with_user(self.doctor)._careos_payload()["encounter_id"], encounter.id)
        self.assertFalse(appointment.with_user(self.reception)._careos_payload()["encounter_id"])
        self.assertFalse([e for e in self.patient.with_user(self.reception).careos_get_profile()["timeline"]
                          if e.get("kind") == "encounter"])
