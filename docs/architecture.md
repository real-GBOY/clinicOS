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
