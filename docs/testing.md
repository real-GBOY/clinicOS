# Testing

All CareOS tests are tagged `careos` and run post-install.

```bash
# Git Bash: MSYS_NO_PATHCONV=1 stops "/careos_base" being rewritten as a Windows path
MSYS_NO_PATHCONV=1 .venv/Scripts/python.exe odoo/odoo-bin -c odoo.conf -d careos_test \
  -i careos --test-enable --test-tags /careos_base,/careos_patients,/careos_appointments,/careos_queue,/careos_clinical,/careos_inventory,/careos_prescriptions,/careos_laboratory,/careos_finance,/careos_communications,/careos_analytics,/careos_ai,/careos_portal,/careos \
  --http-port 8079 --log-level=test
```

(PowerShell needs no prefix.) The browser tour needs Google Chrome and the `websocket-client` package in the venv.

## Coverage

| Suite | What it proves |
|---|---|
| `careos_base/tests/test_careos_base.py` | Branch/department uniqueness, allowed-branch constraint, role implications, session context, branch switching limits, staff cannot edit configuration |
| `careos_patients/tests/test_patient.py` | Patient ID sequence, age, input cleaning, date/phone/email validation, national ID uniqueness, company/branch consistency, duplicate detection, search by ID/phone, change tracking |
| `careos_patients/tests/test_patient_security.py` | Permission matrix per role: read/create/write/unlink, clinical-only conditions and blood type (model + field level), allergy recording, contacts, multi-company isolation, permission-aware global search |
| `careos_patients/tests/test_patient_360.py` | Profile payload per role, retired allergies hidden, timeline (registration, updates, notes, ordering), note escaping, document upload/listing/access |
| `careos_patients/tests/test_ui.py` + tour | End to end as a receptionist in a real browser: shell without Odoo chrome → register → Patient 360 → note → global search |
| `careos_appointments/tests/test_appointment.py` | Creation defaults, required fields, every (state × action) pair of the lifecycle, cancellation reason, no-show and check-in date rules, rescheduling locks, provider/room/patient conflicts incl. across branches, branch/room consistency, booking API, list filters |
| `careos_appointments/tests/test_appointment_security.py` | Role matrix per action, doctor own-schedule, branch isolation (read, write, create), permission-aware appointment search |
| `careos_appointments/tests/test_dashboard_and_patient.py` | Dashboard counts from real records (other branches/days excluded), branch context, role access; Patient 360 next appointment, upcoming/past, lifecycle timeline order, role-limited timelines |
| `careos_appointments/tests/test_ui.py` + tour | Browser: book a follow-up from Patient 360 through the booking dialog |
| `careos_queue/tests/test_queue.py` | Check-in issues tickets, numbering per branch/day, check-in atomicity, no direct ticket edits, full queue flow and appointment sync, invalid queue transitions, board ordering, nurse/doctor/lab permissions, branch isolation, timeline events, dashboard queue metrics |
| `careos_queue/tests/test_ui.py` + tour | Browser: dashboard → appointment → Patient 360 → check in → queue → call → start → complete → timeline → dashboard counts |
| `careos_base/tests/test_notifications.py` | Own-only inbox, dedupe, mark read |
| `careos_base/tests/test_staff.py` | Invite (roles, implied groups, branches, department, history), validation, role/branch edits keep other groups, plain-login accounts, self-protection, last-admin rule, deactivate/reactivate, filters/KPIs, manager read-only + branch scope, reception denied, log not writable |
| `careos_base/tests/test_staff_ui.py` + tour | Browser: admin invites a receptionist, adds the nurse role, deactivates, checks the roles tab |
| `careos_clinical/tests/test_clinical.py` | Encounter opened at check-in, vitals limits/BMI, nurse vitals-only, doctor-only diagnoses, sign-off rules, reception blocked from clinical data, doctor dashboard |
| `careos_inventory/tests/test_inventory.py` | Receive with lots/expiry, status (low / expiring / ok), role checks, low-stock alert once |
| `careos_prescriptions/tests/` | Lifecycle, allergy warnings, pharmacy notification, dispense consumes stock / blocks when short, course completion |
| `careos_laboratory/tests/` | Order -> collect -> results -> verify -> review, flags, role per step, doctor notified |
| `careos_finance/tests/test_finance.py` | Billable lines, invoice creation, post, partial/full payment, refund, statuses, overdue, role matrix |
| `careos_communications/tests/` | Threads, patient-to-reception notifications, reminder scheduling and sending, SMS failure |
| `careos_analytics/tests/` | Manager KPIs from real records, analytics tabs, no-show alert |
| `careos_ai/tests/` | Disabled by default, admin-only config, de-identified context, apply requires review, audit (model call mocked) |
| `careos_portal/tests/` | Portal sees only own data, verified results only, message, reschedule, booking request, staff preview |
| `careos/tests/test_setup.py` | Setup guide steps and admin-only access |
| `careos/tests/test_ui.py` + tours | Browser: doctor visit (vitals, notes, diagnosis, prescription, lab, sign-off); patient portal (message, book) |

## Notes

* Mail tracking is finalized in `cr.precommit`; fixtures run it once so later edits are tracked as updates
  (see `tests/common.py`).
* Appointment and queue tests run on a frozen clock (`freezegun`, 2030-03-12 10:00 UTC) with UTC branches,
  so date rules are deterministic. Browser tours use real time with a UTC branch.
* Odoo's `assertRaises` takes a single exception class, not a tuple.
* The tour sets native date inputs via DOM events; the tour `edit` helper cannot drive them.
