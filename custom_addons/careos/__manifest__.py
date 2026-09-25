{
    "name": "CareOS",
    "summary": "The operating system for modern clinics — full suite and setup guide",
    "description": """
Installs the complete CareOS suite (patients, scheduling, queue, clinical,
prescriptions, laboratory, inventory, finance, communications, analytics,
AI assistance, patient portal) and adds the administrator setup guide.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_portal", "careos_ai"],
    "assets": {
        "web.assets_backend": [
            "careos/static/src/**/*",
        ],
        "web.assets_tests": [
            "careos/static/tests/tours/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
