{
    "name": "CareOS Intelligence",
    "summary": "Assistive AI: summaries, note structuring, operational insight (human-reviewed)",
    "description": """
Contextual AI assistant powered by Claude. Works on de-identified context
built with the user's own access rights, labels every output as
AI-generated, keeps an audit trail, and never writes to the chart without
a doctor's explicit review. Disabled until an administrator enables it.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos_analytics"],
    "external_dependencies": {"python": ["anthropic"]},
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "careos_ai/static/src/**/*",
        ],
    },
    "installable": True,
}
