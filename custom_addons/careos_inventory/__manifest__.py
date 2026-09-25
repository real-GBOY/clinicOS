{
    "name": "CareOS Inventory",
    "summary": "Branch pharmacy and supplies stock on native Odoo Inventory",
    "description": """
Medicines and supplies per branch: stock levels, reorder levels, batch
expiry (FEFO), goods-in, dispensing issues and low-stock / expiry alerts.
Built on Odoo Inventory (quants, lots, reordering rules, pickings).
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_base", "stock", "product_expiry"],
    "data": [
        "security/careos_inventory_security.xml",
        "data/careos_inventory_cron.xml",
    ],
    "demo": [
        "demo/careos_inventory_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_inventory/static/src/**/*",
        ],
    },
    "installable": True,
}
