# Modules

| Module | Status | Depends on | Owns |
|---|---|---|---|
| `careos_base` | Implemented | `web`, `mail` | Branches, departments, role groups, user branch context, design tokens + components, application shell, global search framework |
| `careos_patients` | Implemented | `careos_base` | Patient registry, contacts, allergies, conditions, Patient Directory, Patient 360, patient search provider |
| `careos_appointments` | Implemented | `careos_patients` | Providers, rooms, visit types, appointment lifecycle, conflict-free booking, Appointments workspace (schedule + list), appointment detail, reception dashboard, Patient 360 appointments tab + next-appointment card, appointment search |
| `careos_queue` | Implemented | `careos_appointments` | Queue tickets issued at check-in, queue lifecycle mirrored from appointments, live queue board, queue panel + Waiting metric on the reception dashboard, "Patient called" timeline events |
| `careos_clinical` | Planned | `careos_appointments` | Encounters, vitals, diagnoses, clinical notes |
| `careos_prescriptions` | Planned | `careos_clinical`, `product` | Prescriptions and lines |
| `careos_laboratory` | Planned | `careos_clinical` | Lab test catalogue, orders, results |
| `careos_finance` | Planned | `careos_clinical`, `account` | Healthcare layer over native invoices/payments (no custom invoice model) |
| `careos_communications`, `careos_analytics`, `careos_ai`, `careos_portal` | Later phases | — | — |

Dependency rule: domain modules depend "downwards" only. Cross-module UI integration goes through the
registries and Python hooks, never through imports from a higher module.

| Extension point | Kind | Owner | Used by |
|---|---|---|---|
| `careos.screens` | JS registry | careos_base | every workspace |
| `careos.patient_tabs` | JS registry | careos_patients | appointments tab |
| `careos.patient_overview_cards` | JS registry | careos_patients | next-appointment card |
| `careos.reception_dashboard_panels` | JS registry | careos_appointments | queue panel |
| `careos.search._careos_search_providers()` | Python | careos_base | patients, appointments |
| `careos.patient._careos_timeline_events()` | Python | careos_patients | appointments (lifecycle) |
| `careos.patient.careos_get_profile()` | Python | careos_patients | appointments (next visit, access flags) |
| `careos.appointment._careos_after_transition()` | Python | careos_appointments | queue (issue/sync tickets) |
| `careos.appointment._careos_history()` | Python | careos_appointments | queue ("Patient called") |
| `careos.appointment.careos_reception_dashboard()` | Python | careos_appointments | queue (Waiting KPI, queue panel data) |

## Module layout

```
careos_<domain>/
  models/          one file per model
  security/        ir.model.access.csv + record rules
  data/            sequences, required records
  demo/            synthetic records only
  static/src/      screens/, dialogs/, tabs/, *.css
  static/tests/    tours
  tests/           Python tests (tag: careos)
```
