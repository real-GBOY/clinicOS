import json
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.careos_ai.models.careos_ai import CareosAi
from odoo.addons.careos_appointments.tests.common import FROZEN_NOW
from odoo.addons.careos_clinical.tests.common import CareosVisitCase

NOTE_OUTPUT = {
    "summary": "Hypertension follow-up; BP improved.", "steps": ["Confirm plan"],
    "chief_complaint": "BP follow-up, morning dizziness", "assessment": "Essential hypertension, controlled",
    "plan": "Continue lisinopril; review in 4 weeks", "diagnosis_suggestions": [{"code": "I10", "description": "Essential hypertension"}],
}


@freeze_time(FROZEN_NOW)
@tagged("post_install", "-at_install", "careos")
class TestCareosAi(CareosVisitCase):
    """The provider call is mocked: these tests cover the safety contract,
    not the model."""

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("careos_ai.enabled", "1")
        self.captured = []

        def fake_call(model_self, kind, context):
            self.captured.append((kind, context))
            output = NOTE_OUTPUT if kind == "encounter" else {"summary": "Summary", "steps": ["Step"]}
            return output, "claude-opus-5", "req_test"

        patcher = patch.object(CareosAi, "_careos_call_model", fake_call)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_disabled_by_default(self):
        self.env["ir.config_parameter"].sudo().set_param("careos_ai.enabled", "0")
        with self.assertRaises(UserError):
            self.env["careos.ai"].with_user(self.doctor).careos_assist("patient", self.patient.id)

    def test_patient_context_is_de_identified_and_role_scoped(self):
        self.patient.write({"phone": "+20 100 555 0101", "national_id": "29001011234567"})
        self.env["careos.patient.condition"].create({"patient_id": self.patient.id, "name": "Essential hypertension", "code": "I10"})
        result = self.env["careos.ai"].with_user(self.doctor).careos_assist("patient", self.patient.id)
        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["output"]["summary"], "Summary")
        _kind, doctor_context = self.captured[-1]
        blob = json.dumps(doctor_context, default=str)
        for identifier in (self.patient.name, "555 0101", "29001011234567", self.patient.ref):
            self.assertNotIn(identifier, blob)
        self.assertIn("Essential hypertension", blob)
        # The front desk's context never contains clinical conditions.
        self.env["careos.ai"].with_user(self.reception).careos_assist("patient", self.patient.id)
        self.assertNotIn("Essential hypertension", json.dumps(self.captured[-1][1], default=str))

    def test_note_structuring_needs_human_review(self):
        _appointment, encounter = self.visit()
        encounter.with_user(self.doctor).careos_save({"notes": "BP 132/85, dizzy mornings. Continue lisinopril."})
        Ai = self.env["careos.ai"].with_user(self.doctor)
        result = Ai.careos_assist("encounter", encounter.id)
        # Nothing is written to the chart until the doctor applies it.
        self.assertFalse(encounter.chief_complaint)
        self.assertFalse(encounter.diagnosis_ids)
        applied = Ai.careos_apply_note(result["id"], ["chief_complaint", "plan"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["reviewed_by"], self.doctor.name)
        self.assertEqual(encounter.chief_complaint, "BP follow-up, morning dizziness")
        self.assertEqual(encounter.plan, "Continue lisinopril; review in 4 weeks")
        self.assertFalse(encounter.diagnosis_ids)  # codes are only suggestions
        with self.assertRaises(UserError):
            Ai.careos_apply_note(result["id"], ["plan"])  # already reviewed

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_note_structuring_limited_to_treating_doctor(self):
        _appointment, encounter = self.visit()
        with self.assertRaises(AccessError):
            self.env["careos.ai"].with_user(self.nurse).careos_assist("encounter", encounter.id)
        result = self.env["careos.ai"].with_user(self.doctor).careos_assist("encounter", encounter.id)
        with self.assertRaises(AccessError):
            self.env["careos.ai"].with_user(self.doctor2).careos_apply_note(result["id"], ["plan"])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_roles_and_audit(self):
        with self.assertRaises(AccessError):
            self.env["careos.ai"].with_user(self.lab).careos_assist("patient", self.patient.id)
        result = self.env["careos.ai"].with_user(self.reception).careos_assist("reception", 0)
        self.env["careos.ai"].with_user(self.reception).careos_dismiss(result["id"])
        suggestion = self.env["careos.ai.suggestion"].browse(result["id"])
        self.assertEqual((suggestion.status, suggestion.model_used, suggestion.request_id), ("dismissed", "claude-opus-5", "req_test"))
        with self.assertRaises(AccessError):
            self.env["careos.ai"].with_user(self.reception).careos_configure(True)
