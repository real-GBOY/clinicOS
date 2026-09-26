{
    "name": "CareOS Analytics",
    "summary": "Manager Workspace, operational and financial analytics",
    "description": """
Manager dashboard (revenue, visits, no-show rate, outstanding balance,
department revenue, doctor utilization, operational alert) and the
Analytics screen (operations, finance, patients), computed from live
appointments, queue tickets and posted invoices.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_finance"],
    "data": [
        "data/careos_analytics_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_analytics/static/src/**/*",
        ],
    },
    "installable": True,
}
