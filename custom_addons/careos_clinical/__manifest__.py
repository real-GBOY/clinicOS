{
    "name": "CareOS Clinical",
    "summary": "Encounters, vitals, diagnoses, follow-ups and the Doctor Workspace",
    "description": """
The consultation record: an encounter per visit (opened at check-in),
vitals recorded by nurses or doctors, chief complaint, clinical notes,
plan, diagnoses and follow-up, with doctor sign-off. Adds the Doctor
Workspace, the Encounters list, the Follow-ups list and the Patient 360
clinical history.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_queue"],
    "data": [
        "security/ir.model.access.csv",
        "security/careos_clinical_rules.xml",
        "data/ir_sequence_data.xml",
    ],
    "demo": [
        "demo/careos_clinical_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_clinical/static/src/**/*",
        ],
        "web.assets_tests": [
            "careos_clinical/static/tests/tours/**/*",
        ],
    },
    "installable": True,
}
