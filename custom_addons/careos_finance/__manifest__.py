{
    "name": "CareOS Finance",
    "summary": "Visit billing and payments on native Odoo Accounting",
    "description": """
Invoices generated from the visit (consultation, lab tests, dispensed
medicines) as native account.move records, payment collection at the front
desk, refunds for finance, overdue alerts, Patient 360 billing.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_prescriptions", "careos_laboratory", "account"],
    "data": [
        "security/careos_finance_security.xml",
        "data/careos_finance_data.xml",
    ],
    "demo": [
        "demo/careos_finance_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_finance/static/src/**/*",
        ],
    },
    "installable": True,
}
