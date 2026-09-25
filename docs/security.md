# Security

Every boundary is enforced on the server (ACLs, record rules, field `groups`, explicit `check_access`
in public methods). The UI only mirrors it — hiding a button is never the control.

## Roles

Defined by the spec (§3). Groups live under the **CareOS Role** privilege in `careos_base`.

| Role key | Group | Implies |
|---|---|---|
| reception | `group_careos_reception` | Staff |
| nurse | `group_careos_nurse` | Clinical → Staff |
| doctor | `group_careos_doctor` | Clinical → Staff |
| lab | `group_careos_lab` | Staff |
| pharmacy | `group_careos_pharmacist` | Staff |
| finance | `group_careos_finance` | Staff |
| manager | `group_careos_manager` | Staff |
| admin | `group_careos_admin` | Staff |

Technical groups: `group_careos_user` (Staff — may open CareOS) and `group_careos_clinical` (may read
clinical data). Imaging technician and HR roles arrive with their modules.

## Patients matrix (enforced)

| | Reception | Doctor | Nurse | Lab | Pharmacy | Finance | Manager | Admin |
|---|---|---|---|---|---|---|---|---|
| Patient read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Patient create/edit | ✓ | ✓ | — | — | — | — | — | — |
| Patient delete | — | — | — | — | — | — | — | — |
| Allergies read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Allergies record | — | ✓ | ✓ | — | — | — | — | — |
| Conditions / blood type | — | ✓ | ✓ | — | — | — | — | — |
| Contacts edit | ✓ | ✓ | — | — | — | — | — | — |
| Documents upload / notes | ✓ | ✓ | — | — | — | — | — | — |

Allergies are visible to everyone because they are safety-critical for every role that touches a patient.
Nobody deletes patients or allergies through CareOS; records are archived/retired.

## Appointments and queue matrix (enforced)

| | Reception | Doctor | Nurse | Lab | Pharmacy | Finance | Manager | Admin |
|---|---|---|---|---|---|---|---|---|
| See appointments | branch | own schedule | branch | — | — | — | branch | branch |
| Book / reschedule | ✓ | — | — | — | — | — | — | ✓ |
| Confirm / cancel | ✓ | — | — | — | — | — | — | ✓ |
| Check in / no-show | ✓ | — | — | — | — | — | — | — |
| Start / complete visit | ✓ | own | — | — | — | — | — | — |
| See queue | branch | own patients | branch | — | — | — | branch | branch |
| Call patient | ✓ | own | ✓ | — | — | — | — | — |

"branch" = the user's assigned branches (`careos_branch_ids`); "own" = appointments whose provider is linked
to the user. Three layers enforce this: ACLs (model), record rules (rows: branch or own schedule), and
`ACTION_ROLES` (which role may perform which transition). Clinical content of a visit is reserved
for clinicians by `careos_clinical` (see below).

Conflict detection and ticket numbering use `sudo()` so bookings a user cannot see still count; they return
no data about those bookings (only "provider is already booked" or the next number).

## Clinical, pharmacy, lab, finance (enforced)

| | Reception | Doctor | Nurse | Lab | Pharmacy | Finance | Manager | Admin |
|---|---|---|---|---|---|---|---|---|
| Encounter read | - | ✓ | ✓ | - | - | - | - | - |
| Vitals | - | ✓ | ✓ | - | - | - | - | - |
| Notes, diagnosis, sign-off | - | ✓ | - | - | - | - | - | - |
| Prescribe / issue | - | ✓ | - | - | - | - | - | - |
| Dispense | - | - | - | - | ✓ | - | - | - |
| Receive stock | - | - | - | - | ✓ | - | - | ✓ |
| Inventory read | - | - | - | ✓ | ✓ | ✓ | ✓ | ✓ |
| Order lab | - | ✓ | - | - | - | - | - | - |
| Collect sample | - | - | ✓ | ✓ | - | - | - | - |
| Enter / verify results | - | - | - | ✓ | - | - | - | - |
| Invoices read | ✓ | - | - | - | - | ✓ | ✓ | ✓ |
| Invoice, payment | ✓ | - | - | - | - | ✓ | - | - |
| Refund | - | - | - | - | - | ✓ | - | - |
| Analytics | - | - | - | - | - | ✓ | ✓ | ✓ |

The exact per-action role lists live in each service (`ACTION_ROLES`, `TRANSITIONS`, `VIEW`/`BILL`/`REFUND`
in `careos.billing`) and are covered by the role tests. Reception no longer writes clinical data: check-in
opens the encounter through a controlled `sudo`, and cross-module payloads (appointment -> encounter,
queue -> encounter) look records up with `sudo` and return them only if `has_access` passes for the caller.
Service layers (`careos.billing`, `careos.inventory`, `careos.analytics`, `careos.portal`) check the role
explicitly before any `sudo`.

## Patient portal

Portal users belong to `base.group_portal` only. Every portal route resolves the patient from
`careos.patient.portal_user_id = current user` and never takes a patient id from the client. The portal
shows verified lab results only; payment links use Odoo's native `get_portal_url` access token.

## AI

Off until an admin enables it and sets an API key. The model receives a de-identified context (no names,
patient IDs, phone, e-mail or national ID; free text is scrubbed). Output is labelled
"AI-GENERATED · REQUIRES REVIEW"; nothing reaches a chart until a clinician applies it, and every request,
apply and dismiss is audited in `careos.ai.suggestion`.

## Record rules

All CareOS models carry `company_id` and a multi-company rule (`company_id in company_ids`). Appointments
and queue tickets add branch rules (`branch_id in user.careos_branch_ids`) for front-desk, nurse, manager and
admin roles, and an own-schedule rule for doctors.

## Audit trail

`careos.patient`, allergies and conditions inherit `mail.thread`; identity and clinical fields are tracked,
so every change records who, when, old and new value. Restricted fields (blood type, conditions list) are
not tracked on the patient, so tracking messages never leak clinical data to non-clinical readers.

## Attachments and search

* Patient documents are `ir.attachment` records linked to the patient: Odoo checks access on the linked
  record, so a user who cannot read the patient cannot download its documents. Uploading requires write
  access on the patient.
* `careos.search` runs every provider with the caller's rights and skips models the user cannot read.

## Known gaps

* Field-level restriction of `national_id` and insurance data for non-front-desk roles is not yet applied.
* No read-access audit log (who viewed a record) yet — mail tracking covers writes only.
