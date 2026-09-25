{
    "name": "CareOS Patients",
    "summary": "Patient registry and Patient 360",
    "description": """
Patient identity, contacts, allergies and problem list, with the CareOS
Patient Directory and Patient 360 workspaces.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_base"],
    "data": [
        "security/ir.model.access.csv",
        "security/careos_patient_rules.xml",
        "data/ir_sequence_data.xml",
    ],
    "demo": [
        "demo/careos_patient_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_patients/static/src/**/*",
        ],
        "web.assets_tests": [
            "careos_patients/static/tests/tours/**/*",
        ],
    },
    "installable": True,
}
