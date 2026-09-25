# Modules

| Module | Status | Depends on | Owns |
|---|---|---|---|
| `careos_base` | Implemented | `web`, `mail` | Branches, departments, role groups, user branch context, design tokens + components, application shell, global search framework |
| `careos_patients` | Implemented | `careos_base` | Patient registry, contacts, allergies, conditions, Patient Directory, Patient 360, patient search provider |
| `careos_appointments` | Next | `careos_patients` | Providers, appointment types, schedules, appointment state machine, calendar, check-in |
| `careos_queue` | Planned | `careos_appointments` | Queue tickets and live queue board |
| `careos_clinical` | Planned | `careos_appointments` | Encounters, vitals, diagnoses, clinical notes |
| `careos_prescriptions` | Planned | `careos_clinical`, `product` | Prescriptions and lines |
| `careos_laboratory` | Planned | `careos_clinical` | Lab test catalogue, orders, results |
| `careos_finance` | Planned | `careos_clinical`, `account` | Healthcare layer over native invoices/payments (no custom invoice model) |
| `careos_communications`, `careos_analytics`, `careos_ai`, `careos_portal` | Later phases | — | — |

Dependency rule: domain modules depend "downwards" only. Cross-module UI integration goes through the
registries (`careos.screens`, `careos.patient_tabs`) and Python hooks, never through imports from a
higher module.

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
