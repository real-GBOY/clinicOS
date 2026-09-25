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

## Planned (from the spec's state machines)

| Entity | States |
|---|---|
| Appointment | Draft → Confirmed → Checked-in → In Progress → Completed · Confirmed → Cancelled · Confirmed → No-show |
| Queue ticket | Waiting → Called → In Consultation → Completed · Waiting → No-show |
| Prescription | Draft → Issued → Dispensed → Completed · Issued → Cancelled |
| Lab order | Ordered → Sample Collected → Processing → Result Entered → Verified → Completed |
| Invoice | Native `account.move`: Draft → Posted → Partially Paid → Paid · Posted → Refunded |
