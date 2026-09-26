# CareOS architecture

CareOS is a clinic operations product built on Odoo 19. Odoo provides the ORM,
security model, mail/audit trail, accounting and HR. CareOS owns the domain
model for clinical work and the entire user-facing experience.

## Design source of truth

Claude Design project `e937885f-3a4d-4765-ac4c-4a3fbb0debb5`:

| Artifact | Used for |
|---|---|
| `MediFlow Spec.dc.html` | Roles, information architecture, domain model, state machines, permission matrix, Odoo mapping |
| `MediFlow Prototype.dc.html` | Screen layouts, shell structure, density, component patterns |
| `CareOS Brand & Design System.dc.html` | Colour, type, radius, motion, status badges, wordmark, AI labelling |
| `CareOS Logo - Simplified.dc.html` | Alternative "care◯s" wordmark exploration (not adopted, see below) |

### Resolved inconsistencies

1. **Primary colour.** The prototype uses teal-blue `oklch(48% 0.09 230)`; the brand system defines deep
   teal `oklch(47% 0.1 195)` and says "not hospital blue". CareOS uses the brand system values; the prototype
   supplies layout only.
2. **Wordmark.** The brand system and prototype both use lowercase "care" + an "os" chip in Encode Sans
   Expanded. The simplified-logo file explores a lime ring "o" in a rounded sans. The chip mark is used
   because two artifacts agree and the brand system states the rule explicitly.
3. **Product name.** Spec and prototype files are titled "MediFlow"; the brand system and prototype UI say
   CareOS. The product is CareOS; module prefix `careos_` (the spec's `mediflow_` names are not used).
4. **Status labels.** The prototype shows an appointment "In progress" state while the spec's state machine
   says "In Progress"/"In Consultation". The spec state machine wins; this matters from the appointments slice on.

### Slice 2 decisions (appointments, queue, reception dashboard)

5. **Appointment labels.** Spec state machine names (Draft, Checked-in, In Progress) are used; the brand
   system badge set says "Scheduled" and "In Consultation". Badge colours follow the brand system.
6. **Queue states.** Spec: Waiting, Called, In Consultation, Completed, No-show. No "Skipped" (not specified).
7. **Queue board layout.** The prototype shows three columns (Waiting / In consultation / Completed); called
   patients stay in the Waiting column with a "Called · Room" badge rather than a fourth column.
8. **Reception dashboard.** KPI cards + today's appointments table + quick actions, as in the prototype. The
   prototype "Patient messages" quick action is omitted until communications exist; "In consultation" and
   "Completed" were added as KPIs next to the prototype's four.
9. **Calendar.** The prototype doctor-column calendar is the Appointments "Schedule" view (one day,
   30-minute rows); a List view with filters sits beside it. Week view is deferred.

## Runtime shape

```
Browser
 └─ Odoo web client
     └─ ir.actions.client "careos.app" (target=fullscreen → no Odoo navbar)
         └─ CareOSApp (OWL shell: sidebar, branch context, search, breadcrumbs)
             └─ screen from registry "careos.screens"  ←  registered by domain modules
                 └─ ORM RPC (orm.call / webSearchRead)
                     └─ model methods (careos_* public API)  →  ACLs + record rules  →  PostgreSQL
```

* **Screens are pluggable.** A module adds a workspace with `screenRegistry.add(...)`; the shell builds
  navigation from the registry filtered by the user's CareOS roles. Hiding is cosmetic — the server
  enforces access.
* **Patient 360 is pluggable.** Modules add tabs through the `careos.patient_tabs` registry and timeline
  events by overriding `careos.patient._careos_timeline_events()`.
* **Search is pluggable.** Modules extend `careos.search._careos_search_providers()`; queries run with the
  caller's rights.
* **Screen payloads are server-shaped.** Detail screens call one `careos_get_*` method that returns exactly
  what the screen needs, omitting sections the user may not see, instead of chaining many RPCs.

## Organization model

`res.company` = legal/financial entity (organization). `careos.branch` = physical clinic. Following the spec
(§14.5), branches are a field plus record rules, not separate companies. Patients belong to the organization
and are visible at all its branches; operational records (appointments, queue) will be branch-scoped.

## Module map

See [modules.md](modules.md).

## Architecture governance

These rules keep the architecture coherent as CareOS grows. Reviews check new code against them.

### 1. Layers and dependencies

```
OWL screens (registries)  →  public careos_* methods / portal controllers
   →  authorization (ACL · record rules · field groups · require_role)
   →  domain models (own their state and invariants)
   →  domain services (orchestrate across models)
   →  native Odoo (account.move, stock, mail, portal)
```

* Modules depend **downward only**. A higher module plugs into a lower one through a registry (UI) or an
  overridable hook (Python); a lower module never imports a higher one.
* Use Odoo's objects wherever they fit (invoices, payments, reversals, stock quants, lots, pickings,
  mail, portal). A parallel CareOS model needs a written reason.

### 2. Authorization pipeline

Every public `careos_*` method and every controller treats its arguments as hostile, because it can be
called over RPC with any values. The order is fixed:

1. **Odoo access rights and record rules** apply automatically to non-sudo reads and writes.
2. **Validate arguments** and resolve records **in the caller's scope** (`browse(...)` +
   `check_access`, `has_access`, or a scoped search). Never trust an id, a state or an amount from the
   client. The portal resolves the patient from the logged-in user and never accepts a patient id.
3. **Role check** with `require_role(env, ROLES, message)` from `careos_base.models.authorization`, only
   when the operation is role-specific. Role sets live in the domain module that owns the operation
   (`BILL_ROLES`, `TRANSITIONS[...]`), but they are always evaluated through `has_role` / `require_role`.
   Never write ad-hoc `has_group` chains.
4. **Business invariants**: state machine, validations, amounts.
5. **`sudo()` last**, and only for the narrow read or write that needs it after steps 1–4 passed. A
   record found with `sudo()` is returned to the caller only if the caller `has_access` to it.

`env.su` (internal jobs, demo loading) passes role checks; Odoo system administrators count as CareOS
administrators.

### 3. Services orchestrate, models own invariants

* A **domain model** owns its state machine, validations and per-record logic
  (`account.move._careos_status()`, `careos.appointment._careos_billable_lines()`,
  `careos.encounter.action_complete()`).
* A **service** (`careos.billing`, `careos.inventory`, `careos.staff`, `careos.portal`, `careos.ai`,
  `careos.analytics`, `careos.setup`) authorizes, then orchestrates several models for one use case.
  It does not re-implement a model's rules.
* Warning signs that a service is becoming a "god layer": it computes a record's status, it has
  `if record.state == ...` branches that belong in the model, or it keeps growing unrelated methods.
  Move that logic onto the model.

### 4. Registry governance

Create a JS registry **only when a higher module must extend a lower module's surface** (for example
laboratory adding a panel to the clinical doctor workspace). A component used by its own module stays
local. Each registry has one owner and a documented entry shape. The current set:

| Registry | Owner | Extended by |
|---|---|---|
| `careos.screens`, `careos.dashboards`, `careos.topbar_items`, `careos.sidebar_actions` | careos_base | every module with a screen; ai and portal (topbar, sidebar) |
| `careos.patient_tabs`, `careos.patient_overview_cards` | careos_patients | appointments, clinical, lab, prescriptions, finance, communications, portal |
| `careos.reception_dashboard_panels`, `careos.appointment_sections` | careos_appointments | queue, clinical, finance |
| `careos.queue_ticket_actions` | careos_queue | clinical |
| `careos.encounter_sections`, `careos.encounter_actions`, `careos.doctor_dashboard_panels` | careos_clinical | prescriptions, laboratory |

A new registry is added to this table in the same change.

### 5. Integration boundary

* **Internal** browser ↔ server calls use the ORM (`orm.call` → public `careos_*` methods) and HTTP
  controllers declared with `@http.route(type="jsonrpc")` (portal).
* **External systems** (payment providers, SMS/WhatsApp, labs, insurers, FHIR) connect through a
  dedicated adapter module per integration, built on Odoo's **External JSON-2 API** or on the
  provider's own SDK. Do not build new integrations on the legacy external `/xmlrpc` and `/jsonrpc`
  endpoints: Odoo 19 deprecates them, with removal scheduled for Odoo 22.
* Secrets (API keys, provider credentials) live in `ir.config_parameter` or `odoo.conf`, never in code.

### 6. Demo data

* **Static demo records** (branches, users, patients, providers, rooms) stay in each module's `demo/`
  folder, as usual in Odoo.
* **Generators** that simulate clinic activity live only in the `careos_demo` module, which is installed
  on demo databases (`--with-demo -i careos,careos_demo`) and never in production.

### 7. Tests as a gate

A change is done when the full suite passes on a fresh database. Every feature adds:

* model and state-machine tests;
* the role matrix, both allowed **and** refused;
* branch and company isolation;
* abuse cases in `careos/tests/test_security_abuse.py` for any new public method: forged ids, other
  branches, forged states, restricted fields, invalid amounts, and portal id guessing;
* a browser tour for a new main flow.
