{
    "name": "CareOS Queue",
    "summary": "Live patient queue driven by appointment check-in",
    "description": """
Queue tickets issued at check-in (Waiting, Called, In Consultation,
Completed, No-show), the live queue board, and queue metrics on the
reception dashboard.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_appointments"],
    "data": [
        "security/ir.model.access.csv",
        "security/careos_queue_rules.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_queue/static/src/**/*",
        ],
        "web.assets_tests": [
            "careos_queue/static/tests/tours/**/*",
        ],
    },
    "installable": True,
}
