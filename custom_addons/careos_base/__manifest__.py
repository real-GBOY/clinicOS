{
    "name": "CareOS Base",
    "summary": "CareOS foundation: organization structure, roles, design system and application shell",
    "description": """
CareOS — the operating system for modern clinics.

Provides the platform layer every other CareOS module builds on:
branches and departments, role-based security groups, the design-token
system, and the CareOS application shell (navigation, branch context,
global search).
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "JINX",
    "license": "LGPL-3",
    "depends": ["web", "mail", "auth_signup"],
    "data": [
        "security/careos_security.xml",
        "security/ir.model.access.csv",
        "security/careos_rules.xml",
        "views/careos_templates.xml",
        "views/careos_branch_views.xml",
        "views/careos_menus.xml",
    ],
    "demo": [
        "demo/careos_branch_demo.xml",
        "demo/careos_user_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_base/static/src/scss/tokens.css",
            "careos_base/static/src/scss/components.css",
            "careos_base/static/src/scss/shell.css",
            "careos_base/static/src/components/**/*",
            "careos_base/static/src/search/**/*",
            "careos_base/static/src/shell/**/*",
            "careos_base/static/src/staff/**/*",
        ],
        "web.assets_tests": [
            "careos_base/static/tests/tours/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
