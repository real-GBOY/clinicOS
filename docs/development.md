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
.\.venv\Scripts\python.exe odoo\odoo-bin -c odoo.conf -d careos_demo --with-demo -i careos_queue --stop-after-init

# Upgrade after changing data/views
.\run.ps1 -d careos_demo -u careos_base,careos_patients,careos_appointments,careos_queue
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

Demo providers: Dr. Nourhan Saeed (login `doctor`), Dr. Karim Fathy (`doctor2`), Dr. Mona El-Sayed and
Dr. Hassan Ali (no login). Providers, rooms and visit types are configured under CareOS Configuration.

## Demo schedule

`careos_appointments` demo data books today's clinic at the Cairo branch (09:00–12:00) plus the next two
days, relative to the **install date**; `careos_queue` demo checks four of them in and moves them through the
queue. On later days the dashboard is empty until you seed again:

```python
# odoo-bin shell -d careos_demo
env["careos.appointment"]._careos_demo_schedule(); env["careos.appointment"]._careos_demo_queue(); env.cr.commit()
```

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
