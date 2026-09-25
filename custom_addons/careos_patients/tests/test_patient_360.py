import base64

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import CareosPatientCase


@tagged("post_install", "-at_install", "careos")
class TestPatient360(CareosPatientCase):
    def test_profile_for_doctor_includes_clinical_sections(self):
        profile = self.patient.with_user(self.doctor).careos_get_profile()
        self.assertEqual(profile["name"], "Test Patient")
        self.assertEqual(profile["branch"]["id"], self.branch.id)
        self.assertEqual([a["allergen"] for a in profile["allergies"]], ["Penicillin"])
        self.assertEqual([c["code"] for c in profile["conditions"]], ["I10"])
        self.assertTrue(profile["clinical_access"])
        self.assertTrue(profile["can_edit"])
        self.assertTrue(profile["can_edit_clinical"])

    def test_profile_for_reception_omits_clinical_sections(self):
        profile = self.patient.with_user(self.reception).careos_get_profile()
        self.assertNotIn("conditions", profile)
        self.assertNotIn("blood_type", profile)
        self.assertFalse(profile["clinical_access"])
        self.assertTrue(profile["can_edit"])
        self.assertFalse(profile["can_edit_clinical"])
        # Allergies are safety-critical and stay visible to the front desk.
        self.assertEqual(len(profile["allergies"]), 1)

    def test_profile_for_lab_is_read_only(self):
        profile = self.patient.with_user(self.lab).careos_get_profile()
        self.assertFalse(profile["can_edit"])
        self.assertFalse(profile["can_upload"])

    def test_retired_allergies_are_hidden(self):
        self.allergy.active = False
        self.assertEqual(self.patient.careos_get_profile()["allergies"], [])

    def test_timeline_includes_registration_updates_and_notes(self):
        patient = self.patient.with_user(self.reception)
        patient.write({"phone": "+20 100 555 0199"})
        self.env.flush_all()
        self.env.cr.precommit.run()  # tracking is finalized at commit time
        patient.careos_post_note("Called about insurance renewal.")
        timeline = patient.careos_get_profile()["timeline"]
        titles = [event["title"] for event in timeline]
        self.assertIn("Patient registered", titles)
        self.assertIn("Record updated", titles)
        self.assertIn("Note added", titles)
        self.assertEqual(titles.count("Patient registered"), 1)
        self.assertNotIn("Patient created", titles)
        note = next(e for e in timeline if e["title"] == "Note added")
        self.assertIn("Called about insurance renewal.", note["detail"])
        dates = [event["date"] for event in timeline]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_notes_are_escaped(self):
        self.patient.with_user(self.doctor).careos_post_note("<script>alert(1)</script>\nsecond line")
        body = self.patient.careos_get_messages()[0]["body"]
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("<br>", body.replace("<br/>", "<br>"))

    def test_empty_note_rejected(self):
        with self.assertRaises(ValidationError):
            self.patient.careos_post_note("   ")

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_read_only_roles_cannot_post_notes(self):
        with self.assertRaises(AccessError):
            self.patient.with_user(self.lab).careos_post_note("Not allowed")

    def test_documents_upload_and_list(self):
        data = base64.b64encode(b"%PDF-1.4 synthetic test document").decode()
        attachment_id = self.patient.with_user(self.reception).careos_attach_document("Insurance card.pdf", data)
        documents = self.patient.with_user(self.nurse).careos_get_documents()
        self.assertEqual([d["id"] for d in documents], [attachment_id])
        self.assertEqual(documents[0]["name"], "Insurance card.pdf")
        self.assertEqual(self.patient.careos_get_profile()["document_count"], 1)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_documents_require_write_access_to_upload(self):
        data = base64.b64encode(b"x").decode()
        with self.assertRaises(AccessError):
            self.patient.with_user(self.lab).careos_attach_document("Nope.txt", data)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_documents_hidden_from_non_careos_users(self):
        data = base64.b64encode(b"confidential").decode()
        attachment_id = self.patient.careos_attach_document("Report.pdf", data)
        with self.assertRaises(AccessError):
            self.env["ir.attachment"].with_user(self.outsider).browse(attachment_id).read(["datas"])
