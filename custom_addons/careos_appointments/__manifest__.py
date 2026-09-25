{
    "name": "CareOS Appointments",
    "summary": "Scheduling, appointment lifecycle and the reception dashboard",
    "description": """
Providers, rooms and visit types; appointments with the CareOS lifecycle
(Draft, Confirmed, Checked-in, In Progress, Completed, Cancelled, No-show);
conflict-free booking; the Appointments workspace, the reception dashboard
and Patient 360 integration.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_patients"],
    "data": [
        "security/ir.model.access.csv",
        "security/careos_appointment_rules.xml",
        "data/ir_sequence_data.xml",
        "data/careos_appointment_type_data.xml",
        "views/careos_config_views.xml",
    ],
    "demo": [
        "demo/careos_resource_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_appointments/static/src/**/*",
        ],
        "web.assets_tests": [
            "careos_appointments/static/tests/tours/**/*",
        ],
    },
    "installable": True,
}
