{
    "name": "CareOS Communications",
    "summary": "Patient conversations, appointment reminders and the Inbox",
    "description": """
Patient-facing messages on the patient record (separate from internal
notes), appointment reminders with delivery status through pluggable
providers (e-mail built in), and the Communication Center.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_appointments"],
    "data": [
        "security/ir.model.access.csv",
        "data/careos_communications_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_communications/static/src/**/*",
        ],
    },
    "installable": True,
}
