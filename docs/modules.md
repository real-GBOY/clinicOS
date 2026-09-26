# Modules

| Module | Status | Depends on | Owns |
|---|---|---|---|
| `careos_base` | Implemented | `web`, `mail`, `auth_signup` | Branches, departments, role groups, user branch context, design tokens + components, application shell, global search framework, notifications, Staff & roles (invite, roles, branches, deactivate, access history) |
| `careos_patients` | Implemented | `careos_base` | Patient registry, contacts, allergies, conditions, Patient Directory, Patient 360, patient search provider |
| `careos_appointments` | Implemented | `careos_patients` | Providers, rooms, visit types, appointment lifecycle, conflict-free booking, Appointments workspace (schedule + list), appointment detail, reception dashboard, Patient 360 appointments tab + next-appointment card, appointment search |
| `careos_queue` | Implemented | `careos_appointments` | Queue tickets issued at check-in, queue lifecycle mirrored from appointments, live queue board, queue panel + Waiting metric on the reception dashboard, "Patient called" timeline events |
| `careos_clinical` | Implemented | `careos_queue` | Encounters (opened at check-in), vitals with limits + BMI, diagnoses, notes/plan/follow-up, sign-off, Doctor Workspace dashboard, encounter list, follow-ups, Clinical history tab, nurse vitals from the queue |
| `careos_inventory` | Implemented | `careos_base`, `stock`, `product_expiry` | Medications/supplies on native stock: lots with expiry (FEFO), per-branch warehouse, receive stock, low-stock/expiring status, low-stock cron alerts |
| `careos_prescriptions` | Implemented | `careos_clinical`, `careos_inventory` | Prescriptions and lines, allergy warnings, issue -> pharmacy notification, dispense (consumes stock), course-completion cron, Current medications card |
| `careos_laboratory` | Implemented | `careos_clinical` | Test catalogue with parameters/reference ranges, lab orders from the encounter, worklist (collect -> process -> results -> verify), flagged results, doctor review, Patient 360 Lab tab |
| `careos_finance` | Implemented | `careos_prescriptions`, `careos_laboratory`, `account` | Healthcare layer over native `account.move`/`account.payment`: visit billing, invoices from consultation/lab/medication lines, post, payment register, refunds, overdue cron, Invoices workspace, Patient 360 Billing tab |
| `careos_communications` | Implemented | `careos_appointments` | Patient message threads (chatter subtype), Inbox, e-mail reminders 24 h ahead (cron), reschedule notices, Communication tab |
| `careos_analytics` | Implemented | `careos_finance` | Manager dashboard (revenue MTD, visits, no-show rate, outstanding, department revenue, utilization), Analytics (operations / finance / patients), insight cron, 8-week demo history |
| `careos_ai` | Implemented | `careos_analytics`, Python `anthropic` | Assistive AI drawer (patient, encounter, reception, manager, invoice contexts), de-identified context, audit trail, human review before any chart write, off until an admin enables it |
| `careos_portal` | Implemented | `careos_communications`, `careos_finance`, `portal` | Patient portal at `/careos/portal` (home, appointments + requests, prescriptions, verified lab results, billing / pay now, messages), staff "View as patient" preview, portal invitations |
| `careos` | Implemented | `careos_portal`, `careos_ai` | Meta module: 8-step setup guide, end-to-end browser tours, security abuse suite |
| `careos_demo` | Implemented | `careos` | Demo databases only: generators for the clinic day, queue, visits, prescriptions, lab, stock, invoices, messages, analytics history and the demo portal login |

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
| `careos.dashboards` | JS registry | careos_base | reception, doctor, manager dashboards (`roles`, `defaultFor`) |
| `careos.topbar_items` / `careos.sidebar_actions` | JS registry | careos_base | dashboard tabs, notifications, AI, setup guide, "View as patient" |
| `careos.appointment_sections` / `careos.queue_ticket_actions` | JS registry | appointments / queue | encounter link, billing card, vitals + open encounter |
| `careos.encounter_sections` / `careos.encounter_actions` | JS registry | careos_clinical | prescriptions, lab orders, AI |
| `careos.doctor_dashboard_panels` | JS registry | careos_clinical | pending lab results |
| `careos.appointment.careos_doctor_dashboard()` | Python | careos_clinical | laboratory (pending results panel) |
| `careos.encounter._careos_extend_workspace()` | Python | careos_clinical | prescriptions, laboratory |
| `careos.notification._careos_notify()` | Python | careos_base | pharmacy, lab, reception, inventory, analytics alerts |

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
