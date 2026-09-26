{
    "name": "CareOS Prescriptions",
    "summary": "Prescribing, pharmacy dispensing and current medications",
    "description": """
Prescriptions written in the encounter (Draft, Issued, Dispensed, Completed,
Cancelled), allergy warnings, pharmacy dispensing that issues stock from
the branch store, current medications on Patient 360.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_clinical", "careos_inventory"],
    "data": [
        "security/ir.model.access.csv",
        "security/careos_prescription_rules.xml",
        "data/careos_prescription_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_prescriptions/static/src/**/*",
        ],
    },
    "installable": True,
}
