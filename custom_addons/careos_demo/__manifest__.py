{
    "name": "CareOS Demo Data",
    "summary": "Synthetic clinic activity for demo and showcase databases",
    "description": """
Generates a realistic clinic day and eight weeks of history through the real
CareOS workflows: schedule, queue, consultations, prescriptions, laboratory,
stock, invoices and payments, patient messages, analytics history and a demo
portal login. Synthetic people only.

Install it on demo databases only (``--with-demo -i careos,careos_demo``);
production databases never need it.
""",
    "version": "19.0.1.0.0",
    "category": "CareOS",
    "author": "CareOS",
    "license": "LGPL-3",
    "depends": ["careos"],
    "demo": [
        "demo/careos_demo.xml",
    ],
    "installable": True,
}
