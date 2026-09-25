# Domain model

## Implemented

| Model | Purpose | Key fields | Notes |
|---|---|---|---|
| `careos.branch` | Physical clinic | name, code (unique per company), company_id, timezone, address | Code normalized to upper case |
| `careos.department` | Specialty inside a branch | name, branch_id | Unique name per branch |
| `res.users` (ext.) | Staff branch context | careos_branch_ids (allowed), careos_branch_id (current) | Current must be in allowed |
| `careos.patient` | The patient record | ref (`P-000001`), name, date_of_birth, age (computed), sex, phone, phone_normalized, email, national_id, address, company_id, branch_id (home), insurance_provider, insurance_policy_number, blood_type*, active | `mail.thread` + activities; identity fields tracked |
| `careos.patient.contact` | Next of kin / emergency contact | name, relationship, phone, is_emergency | |
| `careos.patient.allergy` | Allergy | allergen, severity, reaction, active | Retired (active=False), never deleted |
| `careos.patient.condition`* | Problem list entry | name, code (ICD-10 style), status, onset_date, active | Clinical-only |

`*` clinical data, restricted to clinical roles.

### Integrity rules (server-side)

* Patient ID from sequence `careos.patient`; `UNIQUE(ref, company_id)`.
* `UNIQUE(national_id, company_id)`; blank IDs are stored as NULL so they never collide.
* Date of birth not in the future and after 1900; phone ≥ 7 digits; email format.
* Home branch must belong to the patient's company.
* Whitespace in names/IDs normalized on write.
* Duplicate detection (`careos_find_duplicates`): exact national ID, same normalized phone, or same name
  (case/space-insensitive). Advisory at registration, not blocking — two people can share a name.

### Decisions

* **Patient is not a `res.partner`.** Partners are readable by every internal user, which would expose patient
  identity to anyone with an Odoo login. A partner will be linked on demand by the finance module for invoicing.
* **Age is not stored.** It depends on today's date; a stored value would go stale.
* **Patients are organization-scoped**, not branch-scoped: a patient may be seen at any branch of the group.

## Scheduling (careos_appointments)

| Model | Purpose | Key fields |
|---|---|---|
| `careos.room` | Bookable room at a branch | name, branch_id |
| `careos.provider` | Bookable clinician | name, user_id (optional login, unique), specialty, department_id, branch_ids (practices at), default_room_id |
| `careos.appointment.type` | Visit type | name, duration (5–480 min) |
| `careos.appointment` | A booked visit | name (`APT-000001`), patient_id, provider_id, type_id, branch_id, room_id, start, duration, stop (computed), state, reason, notes, cancel_reason, confirmed_at, checked_in_at, started_at, completed_at, cancelled_at, no_show_at |

### Appointment lifecycle

```
Draft --confirm--> Confirmed --check_in--> Checked-in --start--> In Progress --complete--> Completed
Draft, Confirmed --cancel--> Cancelled
Confirmed, Checked-in --no_show--> No-show
```

Spec §6 defines Draft → Confirmed → Checked-in → In Progress → Completed, Confirmed → Cancelled,
Confirmed → No-show. Two documented additions:

* **Draft → Cancelled**: otherwise an unconfirmed booking could never leave the book (deletion is not allowed).
* **Checked-in → No-show**: mirrors the queue rule, so a patient who leaves before being seen does not
  stay "checked in" forever.

Rules enforced in `_careos_transition` and constraints (not in the UI):

| Rule | Where |
|---|---|
| Only the transitions above; `state` cannot be written directly; records are created as Draft | `TRANSITIONS`, `write`, `create` |
| Role per action: confirm/cancel = reception, admin · check-in/no-show = reception · start/complete = reception, doctor · book/reschedule = reception, admin | `ACTION_ROLES` |
| Check-in only on the appointment's branch-local day | `_careos_action_blocker` |
| No-show from Confirmed only after the start time | `_careos_action_blocker` |
| Cancellation needs a reason | `action_cancel` |
| No booking or rescheduling onto a past date (earlier today is allowed) | `_check_bookable_date` |
| Reschedule only while Draft/Confirmed; patient fixed once confirmed | `write` |
| No double-booking of provider, room or patient (Draft/Confirmed/Checked-in/In Progress block the slot; checked across branches with sudo) | `_check_conflicts` |
| Provider must practise at the branch; room at the branch; patient in the same organization; duration 1–480 min | constraints |

"Today" always means the branch-local day (`careos.branch._careos_day_bounds`).

Availability is deliberately minimal: conflicts are prevented and the booking dialog shows a provider's busy
slots; provider working hours and rotas are not modelled yet.

## Queue (careos_queue)

`careos.queue.ticket`: appointment_id (unique), patient/provider/branch (stored related), queue_date
(branch-local), number (per branch per day, allocated under a row lock), state, room_id, checked_in_at,
called_at, called_by_id, started_at, completed_at, no_show_at.

```
Waiting --call--> Called --start--> In Consultation --complete--> Completed
Waiting, Called --no_show--> No-show
```

Spec §6: Waiting → Called → In Consultation → Completed · Waiting → No-show. Addition: Called → No-show
(called but never came). There is no "Skipped" state because the spec has none.

* Tickets are created only by appointment check-in, in the same transaction (tested: if ticket creation
  fails, the check-in rolls back).
* Only **call** is a queue-only transition. Start/complete/no-show are appointment transitions; the ticket
  mirrors them through `_careos_after_transition`, so appointment and ticket can never disagree.
* Starting straight from Waiting (a doctor fetches the patient) records an implicit call.

## Planned

| Entity | States |
|---|---|
| Prescription | Draft → Issued → Dispensed → Completed · Issued → Cancelled |
| Lab order | Ordered → Sample Collected → Processing → Result Entered → Verified → Completed |
| Invoice | Native `account.move`: Draft → Posted → Partially Paid → Paid · Posted → Refunded |
