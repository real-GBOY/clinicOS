{
    "name": "CareOS Laboratory",
    "summary": "Lab ordering, worklist, result entry and review",
    "description": """
Test catalogue with reference ranges, lab orders from the encounter
(Ordered, Sample Collected, Processing, Result Entered, Verified,
Completed), result entry with abnormal flags, doctor review, and the
Laboratory worklist.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_clinical", "product"],
    "data": [
        "security/ir.model.access.csv",
        "security/careos_lab_rules.xml",
        "data/careos_lab_catalogue.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_laboratory/static/src/**/*",
        ],
    },
    "installable": True,
}
