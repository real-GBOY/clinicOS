# Development

## Environment

* Odoo 19.0 source in `odoo/` (not versioned here), Python 3.12 venv in `.venv/`.
* PostgreSQL 18 on localhost, role `odoo`/`odoo`. `odoo.conf` sets `db_template = template1`
  (Windows PostgreSQL rejects Odoo's default template0 collation).
* CareOS modules live in `custom_addons/`.

## Common commands (PowerShell)

```powershell
# Run the dev server on the default database
.\run.ps1

# Fresh demo database with CareOS installed (demo users/patients are synthetic)
.\.venv\Scripts\python.exe odoo\odoo-bin -c odoo.conf -d careos_demo --with-demo -i careos_patients --stop-after-init

# Upgrade after changing data/views
.\run.ps1 -d careos_demo -u careos_base,careos_patients
```

Open CareOS at `/odoo/action-careos_base.action_careos_app` (it is also the home action of demo users).

## Demo accounts (demo databases only — password = login)

| Login | Role | Branches |
|---|---|---|
| reception | Receptionist | Cairo, Alexandria |
| doctor | Doctor | Cairo |
| doctor2 | Doctor | Cairo, Menoufia |
| nurse | Nurse | Cairo |
| lab | Lab Technician | Cairo |
| manager | Clinic Manager | all |
| admin | CareOS System Administrator + Odoo admin | all |

## Adding a screen

```js
import { screenRegistry } from "@careos_base/shell/screen_registry";
screenRegistry.add("queue", {
    label: "Queue", navGroup: "operations", sequence: 20,
    roles: ["reception", "nurse", "doctor"],   // navigation only
    Component: QueueBoard,                     // receives { params }
});
```

Inside a screen: `this.env.careos.navigate(id, params)`, `this.env.careos.session`,
`this.env.careos.setPageTitle(title)`.

## Conventions

* Public RPC methods on models are prefixed `careos_` and call `check_access` explicitly.
* Plain CSS with tokens (no SCSS needed); class prefix `co-`.
* Never put real patient data in demo files.
