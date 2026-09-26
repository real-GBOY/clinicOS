{
    "name": "CareOS Patient Portal",
    "summary": "Patient portal and staff 'View as patient' preview",
    "description": """
Patients see their appointments, prescriptions, verified lab results,
invoices (with online payment through the Odoo invoice portal) and
messages, request appointments and reschedules. Staff preview any
patient's portal read-only and invite patients from Patient 360.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_communications", "careos_finance", "portal"],
    "data": [
        "views/careos_portal_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_portal/static/src/portal/**/*",
            "careos_portal/static/src/backend/**/*",
        ],
        "web.assets_frontend": [
            "careos_base/static/src/scss/tokens.css",
            "careos_base/static/src/scss/components.css",
            "careos_laboratory/static/src/lab.css",
            "careos_communications/static/src/communications.css",
            "careos_appointments/static/src/appointments.css",
            "careos_portal/static/src/portal/**/*",
            "careos_portal/static/src/frontend/**/*",
        ],
        "web.assets_tests": [
            "careos_portal/static/tests/tours/**/*",
        ],
    },
    "installable": True,
}
