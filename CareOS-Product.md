# CareOS — Product Book

> **The operating system for modern clinics.**
> One system for the front desk, the doctor's room, the lab, the pharmacy, the finance office, the manager
> and the patient, built on Odoo 19.

This document describes everything CareOS is and does: who it is for, every role, screen and flow, the
rules behind them, how data and permissions work, how it is built, how to run it, what is tested, what is
missing, and where it goes next. It describes the product as it is implemented today.

---

## Table of contents

1. [Product summary](#1-product-summary)
2. [The problem and who it is for](#2-the-problem-and-who-it-is-for)
3. [Product principles](#3-product-principles)
4. [Roles](#4-roles)
5. [The application at a glance](#5-the-application-at-a-glance)
6. [Feature catalogue](#6-feature-catalogue)
7. [End-to-end flows](#7-end-to-end-flows)
8. [State machines](#8-state-machines)
9. [Permissions](#9-permissions)
10. [Data model](#10-data-model)
11. [Notifications and automation](#11-notifications-and-automation)
12. [AI assistance](#12-ai-assistance)
13. [Patient portal](#13-patient-portal)
14. [Design system](#14-design-system)
15. [Architecture](#15-architecture)
16. [Modules](#16-modules)
17. [Security, privacy and compliance](#17-security-privacy-and-compliance)
18. [Installation and operations](#18-installation-and-operations)
19. [Demo and showcase data](#19-demo-and-showcase-data)
20. [Quality and testing](#20-quality-and-testing)
21. [Known limitations](#21-known-limitations)
22. [Roadmap](#22-roadmap)
23. [Glossary](#23-glossary)

---

## 1. Product summary

| | |
|---|---|
| **Product** | CareOS |
| **Category** | Clinic management / practice operating system |
| **Target** | Outpatient clinics and multi-branch clinic groups (first market: Egypt) |
| **Platform** | Odoo 19 (Python 3.12, PostgreSQL, OWL web framework) |
| **Users** | Reception, doctors, nurses, lab technicians, pharmacists, finance, managers, administrators, patients |
| **Delivery** | 14 Odoo modules; the `careos` meta module installs the full suite |
| **Status** | Feature-complete against the product prototype; 180 automated tests passing |
| **License** | LGPL-3.0 (as declared in the module manifests) |
| **Repository** | https://github.com/real-GBOY/clinicOS |

CareOS covers the whole outpatient day:

1. **Before the visit:** registration, booking, reminders.
2. **At the visit:** check-in, queue, vitals, consultation, prescriptions and lab orders.
3. **Supporting teams:** lab worklist, pharmacy dispensing, stock.
4. **Money:** invoices, payments, refunds.
5. **Oversight:** dashboards and analytics.
6. **Patient side:** a portal with results, prescriptions, bills and messages.

Every screen reads and writes real records. There is no mock UI.

---

## 2. The problem and who it is for

### The problem

Most clinics run on a mix of paper files, spreadsheets, WhatsApp groups and a billing program that knows
nothing about the medical record. The consequences:

- The front desk re-types patient details and cannot see who is already waiting.
- Doctors lose time finding past visits, results and current medication.
- Lab and pharmacy learn about new orders by someone walking over.
- Invoices miss items (a lab test, a dispensed medicine), and nobody sees unpaid balances.
- Managers cannot answer "how many no-shows this month" or "which doctor is overbooked".
- Patients phone the clinic for every result, appointment change or bill.

### Who it is for

| Segment | Fit |
|---|---|
| Single-specialty clinic (1 branch, 2–6 doctors) | Full fit: install, run the setup guide, start |
| Multi-specialty polyclinic | Full fit: departments, several providers, shared lab and pharmacy |
| Clinic group (several branches) | Full fit: per-branch data, staff assigned to branches, group-level manager view |
| Hospitals (inpatient, theatre, wards) | Out of scope today |

---

## 3. Product principles

1. **One workspace per role.** Each person lands on the screen for their job and sees only what they
   need. Staff never see the generic Odoo back office.
2. **The server enforces every rule.** Permissions, workflow steps and validations live on the server.
   Hiding a button is never the only protection.
3. **Real data only.** Every number, list and chart comes from the database. Empty states are honest.
4. **One record, many views.** A visit is a single chain: appointment → queue ticket → encounter →
   prescriptions / lab orders → invoice. Each team works on its own part of the same chain.
5. **Use the platform.** Accounting, stock, email, portal and security come from Odoo, not from
   parallel reinventions.
6. **Assistive AI, never autonomous.** AI suggests; a human reviews and applies. It is off until an admin
   enables it.
7. **Auditability.** Who changed what, when, and from what to what, for clinical, identity and access data.

---

## 4. Roles

CareOS has eight staff roles plus the patient. A staff member can hold several roles (for example
Reception + Finance at a small clinic).

| Role | Mission | Lands on | Key powers |
|---|---|---|---|
| **Reception** | Run the front desk | Reception dashboard | Register and edit patients; book, confirm, reschedule, cancel; check in; run the queue; invoice and take payments; reply to patient messages |
| **Doctor** | Treat patients | Doctor workspace | Own schedule and queue; consultation notes, diagnoses, sign-off; prescribe; order and review lab tests; follow-ups |
| **Nurse** | Clinical support | Queue | Call patients; record vitals; read clinical records; collect lab samples |
| **Laboratory** | Produce results | Lab worklist | Collect → process → enter results → verify |
| **Pharmacy** | Dispense and stock | Prescriptions / Inventory | Dispense issued prescriptions; receive stock with batch and expiry; stock alerts |
| **Finance** | Money | Invoices | Invoices, payments, refunds, overdue follow-up, finance analytics |
| **Manager** | Oversight | Manager dashboard | KPIs, analytics, read access to operations, invoices, inventory and staff (own branches) |
| **Administrator** | Configure and govern | Setup guide / Staff & roles | Clinic configuration, staff invitations and roles, AI enablement, receive stock |
| **Patient** | Self-service | Patient portal | Appointments and requests, prescriptions, verified results, bills and online payment, messages |

---

## 5. The application at a glance

### Staff app (full screen)

```
┌────────────┬──────────────────────────────────────────────────────────────┐
│ care os    │ Cairo Branch ▾ / Page      [ Search… Ctrl K ]   🔔   AI       │
│            ├──────────────────────────────────────────────────────────────┤
│ OVERVIEW   │                                                              │
│  Dashboard │                    Current screen                            │
│ CLINICAL   │                                                              │
│  Patients  │                                                              │
│  Follow-ups│                                                              │
│  …         │                                                              │
│ SETTINGS   │                                                              │
│  Staff     │                                                              │
│            │                                                              │
│ Setup guide│                                                              │
│ View as    │                                                              │
│  patient → │                                                              │
│ 👤 Name    │                                                              │
└────────────┴──────────────────────────────────────────────────────────────┘
```

- **Sidebar:** navigation grouped as Overview, Clinical, Operations, Finance, Inventory, Communication,
  Analytics and Settings, filtered by role. Admins also get the Setup guide, and staff with patient
  access get "View as patient".
- **Topbar:**
  - branch switcher and breadcrumb;
  - global search / command palette (`Ctrl K`);
  - dashboard tabs, when a user has more than one dashboard;
  - notifications bell;
  - AI Assistant.
- **Responsive:** works down to phone width (collapsible navigation, tables that hide secondary columns).

### Screen inventory

| Area | Screen | Main users |
|---|---|---|
| Overview | Reception dashboard | Reception, nurse |
| | Doctor workspace | Doctor |
| | Manager dashboard | Manager, admin |
| Clinical | Patient directory | All staff |
| | Patient 360 (with tabs) | All staff (tabs by role) |
| | Encounters list | Doctor, nurse |
| | Consultation (encounter workspace) | Doctor, nurse |
| | Follow-ups | Doctor, reception |
| | Prescriptions list and detail | Doctor, pharmacy |
| | Lab worklist and order detail | Lab, doctor, nurse |
| Operations | Appointments (day schedule and list) | Reception, doctor, nurse, manager |
| | Appointment detail | Reception, doctor, nurse |
| | Live queue | Reception, nurse, doctor |
| Finance | Invoices list and invoice detail | Reception, finance, manager |
| Inventory | Inventory | Pharmacy, lab, finance, manager, admin |
| Communication | Inbox (Communication Center) | Reception |
| Analytics | Analytics: Operations / Finance / Patients | Manager, finance, admin |
| Settings | Staff & roles | Admin (manage), manager (read) |
| | Setup guide (8 steps) | Admin |
| Patient | Patient portal: Home, Appointments, Prescriptions, Lab Results, Billing, Messages | Patient |
| | Portal preview ("View as patient") | Staff |

---

## 6. Feature catalogue

### 6.1 Organisation and configuration

- **Company → branches → departments.** Each branch has:
  - a code and a timezone;
  - working days and opening hours (for example Saturday–Thursday, 09:00–22:00);
  - its own stock warehouse.
- **Staff** are assigned to one or more branches and have a current branch they can switch between. They
  only see operational data for their branches. A default department appears in the header.
- **Providers** are doctors, each with a specialty, department, branches and a default room. A provider
  can be linked to a login.
- **Rooms** and **visit types** (New patient, Follow-up, Consultation), each visit type with a duration
  and a price.
- **Setup guide.** Eight guided steps for a new clinic:
  1. Organisation (name, country).
  2. Branch (name, code, timezone).
  3. Departments.
  4. Doctors (with optional invitation).
  5. Working hours.
  6. Visit types.
  7. Prices (visit types and lab tests).
  8. Staff invitations.

### 6.2 Staff & roles

- **Staff list:**
  - counts of active staff, pending invitations, deactivated accounts and administrators;
  - search, role filter and status filter (Active / Invited / Deactivated / All);
  - for each person: roles, branches, department and last sign-in.
- **Invite staff:** name, work email, one or more roles, branches, default branch and department. The
  person receives an email to **set their own password**. No one else ever sees or sets it.
- **Edit** roles, branches, department, name and sign-in. **Deactivate / reactivate** accounts. **Resend**
  invitations.
- **Access history** per person: who changed which roles or branches, and when.
- **Roles & permissions tab:** what each role can do, and who holds it.
- **Safeguards:**
  - no self-demotion or self-deactivation;
  - always at least one active administrator;
  - every account keeps at least one role and one branch (remove access by deactivating);
  - only CareOS role groups are changed.

### 6.3 Patients

- **Registration:**
  - name, date of birth (age computed), sex, phone, email, national ID, address, home branch, insurance
    provider and policy, blood type;
  - input is cleaned and validated (phone, email, date);
  - **duplicate detection** warns about matching patients before a new record is created.
- **Patient ID** sequence (e.g. `P-000055`).
- **Allergies** (allergen, severity, reaction) are visible to everyone who touches the patient. Severe
  allergies show as a red badge in the header.
- **Conditions** (name, ICD-style code, status: active / controlled / resolved) are visible to clinical
  roles only.
- **Contacts** (e.g. spouse, emergency contact), **documents** (uploads), **notes**.
- **Patient Directory:** search by name, ID or phone; branch or all-branches scope; paging.
- **Patient 360:** one page per patient.
  - Header: identity, allergy badge, insurance.
  - Tabs: **Overview**, **Appointments**, **Clinical history**, **Lab results**, **Billing**,
    **Communication**, **Documents**, **Notes**. Tabs appear by role.
  - Overview cards: next appointment, current medications, portal access, allergies, identity and
    contacts.
  - **Timeline** of everything that happened: registration, bookings, check-ins, consultations,
    prescriptions, lab results, invoices, messages, changes.

### 6.4 Appointments

- **Day schedule:** one column per doctor, colour-coded by status. There is also a **list view** with
  filters by provider, status, date and text search.
- **Booking:**
  - patient, doctor, visit type, date and time, room, reason;
  - the dialog shows each doctor's busy slots;
  - **conflicts are blocked**: the same doctor, room or patient cannot be double-booked, even across
    branches;
  - bookings are limited to branch working days and hours.
- **Lifecycle actions:** confirm, check in, start, complete, cancel (a reason is required), mark as
  no-show, reschedule (locked once the visit has started).
- **Appointment detail:** status, times, room, reason, history, linked encounter and billing card.
- **Reminders** are scheduled automatically 24 h before confirmed appointments. Rescheduling notifies the
  doctor.

### 6.5 Check-in and live queue

- **Check-in** issues a **numbered queue ticket** (per branch, per day) and **opens the encounter** in
  the same step.
- **Live queue board** has three columns:
  - **Waiting** (with the wait time in minutes and a "Called · Room" badge);
  - **In consultation** (showing "since" time);
  - **Completed today**.
- Actions: call patient, start consultation, complete visit, no-show. Nurses can record vitals straight
  from a ticket, and clinicians can open the encounter.
- The reception dashboard shows the queue as it happens. The board refreshes automatically.

### 6.6 Consultation (encounter)

- **Vitals:** blood pressure, heart rate, temperature, weight, height, SpO2, respiratory rate. BMI is
  computed and ranges are validated on the server. Nurses record vitals; doctors can update them.
- **Chief complaint, clinical notes, plan, follow-up** (date and reason). Changes are autosaved.
- **Diagnoses** with codes (e.g. `I10 Essential hypertension`) and a primary flag. Only doctors can add
  them.
- **Prescriptions** and **lab orders** are created from inside the consultation.
- **Previous encounters** for context. The patient's allergies and conditions appear as badges.
- **Sign-off** requires a diagnosis. It completes the appointment and makes the record **read-only**
  ("Signed off by Dr. …").
- **Doctor workspace** has:
  - today's schedule with an "Open" action;
  - pending lab results waiting for review;
  - follow-ups due this week.

### 6.7 Prescriptions and pharmacy

- **Prescriptions** have one or more lines: medicine, dose, frequency, duration, quantity, instructions.
- **Allergy warning** when the patient has a recorded allergy.
- **Issue** makes the prescription read-only and **notifies the pharmacy**. Changing it afterwards means
  cancelling and writing a new one.
- **Dispense** (pharmacist) consumes stock **first-expiry-first-out**. It is blocked when stock is
  insufficient.
- **Courses complete automatically** after the longest line's duration (daily job).
- **Current medications** card on Patient 360. The portal shows active prescriptions.

### 6.8 Laboratory

- **Test catalogue** with parameters, units and reference ranges. Seeded tests (price in EGP):

  | Test | Parameters | Price |
  |---|---|---|
  | Lipid Panel | Total cholesterol, LDL, HDL, Triglycerides | 600 |
  | CBC | Haemoglobin, WBC, Platelets | 250 |
  | Fasting Glucose | Fasting glucose | 80 |
  | HbA1c | HbA1c | 300 |
  | Thyroid Panel | TSH, Free T4 | 450 |

- **Orders** from the consultation: tests, priority (routine / urgent) and a clinical note.
- **Worklist:** Active / Completed views, urgent flag, and an order panel with result entry (save draft,
  release).
- **Results** are **flagged** low, high or normal against the reference range.
- **Verification** by the lab. **Review** by the ordering doctor, who is notified when results are ready.
- Only **verified** results reach the patient portal.

### 6.9 Inventory

- Medicines, supplies and lab consumables on Odoo stock. Each item has:
  - an item type and strength;
  - batch (lot) tracking with **expiry dates**;
  - a per-branch **reorder level**.
- **Overview:** total items, low stock and expiring within 30 days. Each item shows stock, reorder level,
  expiry and status (OK / Low stock / Expiring soon).
- **Receive stock** with quantity, batch number and expiry date.
- **Low-stock alerts** go to pharmacists via a scheduled job, at most once per item.

### 6.10 Billing and payments

- Built on **native Odoo invoices** (`account.move`) and payments.
- **Visit billing:** one click turns a completed visit into an invoice with its lines:
  - consultation fee (by visit type);
  - lab tests;
  - dispensed medication.
- **Statuses:** Draft, Pending, Partially paid, Paid, Overdue, Refunded.
- **Record payment:** full or partial, by cash or card, with payment history.
- **Refunds** (finance only) are recorded as credit notes with a reason.
- **Overdue detection:** a daily job flags overdue invoices and notifies finance.
- **Invoices workspace:** search; Unpaid / Paid / Draft / All filters; totals and balances.
- **Patient 360 Billing tab** and the patient's balance due. The portal has a **Pay now** link through
  Odoo's secure payment page.

### 6.11 Communications

- **Patient messages:** two-way threads between the patient (portal) and the clinic. Staff replies go by
  email when the patient has an address.
- **Communication Center (Inbox):** conversation list with unread markers, the thread, a reply box and
  a link to Patient 360.
- **Reminders:** email reminders 24 h before visits, sent by a job every 10 minutes, with status
  (scheduled / sent / failed / cancelled) and retry. SMS is modelled but needs a provider.
- A new patient message notifies reception.

### 6.12 Dashboards and analytics

- **Reception dashboard:**
  - counts of today's appointments, checked in, waiting, in consultation, completed and no-shows;
  - today's appointments with inline check-in;
  - quick actions (register, book);
  - the queue as it happens.
- **Doctor workspace:** see 6.6.
- **Manager dashboard:**
  - revenue this month vs last month;
  - patient visits;
  - no-show rate (percentage-point change);
  - outstanding balance and number of unpaid invoices;
  - revenue by department;
  - doctor utilisation (booked time vs opening hours);
  - an operational alert when a department's no-show rate is about twice the branch average.
- **Analytics** for the last 7/30/90 days:
  - **Operations:** no-show rate by department, average wait time (check-in → consultation).
  - **Finance:** revenue and collections.
  - **Patients:** volumes and trends.

### 6.13 Search, notifications and navigation

- **Command palette** (`Ctrl K`) searches patients, appointments, encounters, prescriptions, lab orders
  and invoices. Results depend on the user's permissions.
- **Notifications bell:** per-user, with unread counts, mark read / mark all read, and a link to the
  record.
- **Branch switcher** limited to the user's assigned branches.

---

## 7. End-to-end flows

### 7.1 The patient visit (happy path)

```
Reception            Nurse               Doctor                    Lab / Pharmacy         Reception / Finance
─────────            ─────               ──────                    ──────────────         ───────────────────
Register patient
Book appointment ──► (reminder 24h)
Confirm
Check in ─────────► ticket #021 issued, encounter opened
                     Call patient
                     Record vitals
                                         Start consultation
                                         Complaint, notes, plan
                                         Diagnosis
                                         Prescription → Issue ──► Pharmacy notified
                                         Lab order ─────────────► Worklist
                                         Sign off (read-only)
                                                                   Dispense (stock ↓)
                                                                   Collect → Process →
                                                                   Results → Verify ──► Doctor notified → Review
Invoice (consultation + lab + medicines) → Post → Payment (full/partial)
Patient sees verified results, prescriptions and balance in the portal; pays online; messages the clinic
```

### 7.2 Walk-in

Reception books the patient for "now" and checks them in right away. From there the flow is identical.

### 7.3 Cancellation, no-show, reschedule

- **Cancel** needs a reason (patient request, rebooked, provider unavailable…).
- **No-show** can be marked once the appointment time has passed. It feeds the no-show analytics.
- **Reschedule** is allowed before the visit starts. The doctor is notified and reminders are rescheduled.

### 7.4 Pharmacy

Issued prescriptions appear in the pharmacy list, and the pharmacist is notified. **Dispense** takes
stock by earliest expiry. If stock is short, dispensing is blocked and the prescription stays issued.
Receiving stock needs a batch number and expiry date for tracked medicines.

### 7.5 Laboratory

Doctor orders (routine or urgent) → nurse or lab collects the sample → lab processes → enters results
(values outside the reference range are flagged) → verifies → the doctor is notified, reviews, and the
order completes. The patient sees verified results in the portal.

### 7.6 Billing

Completed visit → **Create invoice** (lines gathered automatically) → **Post** → **Record payment**
(cash or card, partial allowed) or **Pay now** from the portal. The daily overdue job flags late invoices.
Finance can **refund** with a reason.

### 7.7 Patient self-service

The patient logs in to the portal and can:
- see the next appointment and **reschedule** it, or **book new** (creates a request that reception
  confirms);
- read active prescriptions and verified lab results;
- see invoices and **pay now**;
- message the clinic.

### 7.8 Clinic onboarding

The administrator installs CareOS, completes the **8-step setup guide**, and invites staff from
**Staff & roles**. Staff set their password from the email and land on their own workspace.

---

## 8. State machines

Only the transitions below are possible. Each one is enforced on the server with a role check.

**Appointment**
```
Draft ──confirm──► Confirmed ──check_in──► Checked-in ──start──► In Progress ──complete──► Done
  │                   │                        │
  └──cancel──► Cancelled ◄──cancel──┘          └──no_show──► No-show   (also from Confirmed)
```

**Queue ticket** (mirrors the appointment; only *call* is queue-specific)
```
Waiting ──call──► Called ──start──► In Consultation ──complete──► Completed
Waiting, Called ──no_show──► No-show
```

**Encounter**
```
Open ──sign-off (needs a diagnosis)──► Done (read-only)
```

**Prescription**
```
Draft ──issue──► Issued ──dispense──► Dispensed ──(course ends, daily job)──► Completed
Draft, Issued ──cancel──► Cancelled
```

**Lab order**
```
Ordered ──collect──► Sample Collected ──process──► Processing ──enter results──► Result Entered
        ──verify (lab)──► Verified ──review (doctor)──► Completed
```

**Invoice** (derived from native accounting)
```
Draft ──post──► Pending ──partial payment──► Partially paid ──payment──► Paid
Pending / Partially paid ──past due date──► Overdue
Paid ──refund──► Refunded
```

**Staff account**
```
Invited (never signed in) ──first sign-in──► Active ──deactivate──► Deactivated ──reactivate──► Active/Invited
```

---

## 9. Permissions

"✓" = allowed, "branch" = the user's assigned branches, "own" = the doctor's own patients and schedule.

### Patients

| | Reception | Doctor | Nurse | Lab | Pharmacy | Finance | Manager | Admin |
|---|---|---|---|---|---|---|---|---|
| Read patient | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create / edit patient | ✓ | ✓ | – | – | – | – | – | – |
| Delete patient | – | – | – | – | – | – | – | – |
| Allergies: read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Allergies: record | – | ✓ | ✓ | – | – | – | – | – |
| Conditions / blood type | – | ✓ | ✓ | – | – | – | – | – |
| Documents, notes | ✓ | ✓ | – | – | – | – | – | – |

### Appointments and queue

| | Reception | Doctor | Nurse | Lab | Pharmacy | Finance | Manager | Admin |
|---|---|---|---|---|---|---|---|---|
| See appointments | branch | own | branch | – | – | – | branch | branch |
| Book / reschedule / confirm / cancel | ✓ | – | – | – | – | – | – | ✓ |
| Check in / no-show | ✓ | – | – | – | – | – | – | – |
| Start / complete visit | ✓ | own | – | – | – | – | – | – |
| Call patient | ✓ | own | ✓ | – | – | – | – | – |

### Clinical, pharmacy, lab, finance

| | Reception | Doctor | Nurse | Lab | Pharmacy | Finance | Manager | Admin |
|---|---|---|---|---|---|---|---|---|
| Read encounters | – | ✓ | ✓ | – | – | – | – | – |
| Vitals | – | ✓ | ✓ | – | – | – | – | – |
| Notes, diagnosis, sign-off | – | ✓ | – | – | – | – | – | – |
| Prescribe / issue | – | ✓ | – | – | – | – | – | – |
| Dispense | – | – | – | – | ✓ | – | – | – |
| Receive stock | – | – | – | – | ✓ | – | – | ✓ |
| Read inventory | – | – | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Order lab tests | – | ✓ | – | – | – | – | – | – |
| Collect sample | – | – | ✓ | ✓ | – | – | – | – |
| Enter / verify results | – | – | – | ✓ | – | – | – | – |
| Read invoices | ✓ | – | – | – | – | ✓ | ✓ | ✓ |
| Create invoice / take payment | ✓ | – | – | – | – | ✓ | – | – |
| Refund | – | – | – | – | – | ✓ | – | – |
| Analytics | – | – | – | – | – | ✓ | ✓ | ✓ |

### Administration

| | Admin | Manager | Others |
|---|---|---|---|
| Setup guide, configuration | ✓ | – | – |
| Staff list and history | all staff | own branches (read-only) | – |
| Invite, change roles/branches, deactivate | ✓ | – | – |
| Enable AI | ✓ | – | – |

**How it is enforced (four layers):**
1. **Access rules:** which role may read, create, edit or delete each kind of record.
2. **Record rules:** which rows (branch, own schedule, own patient record, company).
3. **Field restrictions:** clinical-only fields such as conditions and blood type.
4. **Workflow role checks** inside every action, plus service layers that check the caller's role before
   any elevated read.

---

## 10. Data model

### Core entities

| Entity | Purpose | Key fields |
|---|---|---|
| Branch | A clinic location | name, code, timezone, working days, opening hours, warehouse |
| Department | Specialty unit in a branch | name, branch |
| Staff user | Odoo user + CareOS context | roles, allowed branches, current branch, department |
| Staff access log | Audit of access changes | staff member, actor, summary, date |
| Patient | The person treated | patient ID, name, DOB, sex, phone, email, national ID, address, home branch, insurance, blood type, portal user |
| Allergy / Condition / Contact | Patient details | allergen + severity + reaction / name + code + status / name + relation + phone |
| Provider | A doctor | name, specialty, department, branches, default room, user |
| Room, Visit type | Resources | room per branch; visit type with duration, price, service product |
| Appointment | A booked visit | patient, provider, branch, room, type, start/stop, reason, state, lifecycle timestamps, cancel reason |
| Queue ticket | Position in today's queue | appointment, number, queue date, state, called by, lifecycle timestamps |
| Encounter | The consultation record | appointment, vitals, BMI, complaint, notes, plan, follow-up, state, signed-off by |
| Diagnosis | Coded diagnosis | encounter, code, description, primary |
| Prescription / line | Medication order | encounter, state, lines (product, dose, frequency, duration, quantity, instructions), issued/dispensed info, stock picking |
| Lab test / parameter | Catalogue | name, code, price; parameter unit and reference range |
| Lab order / result | Lab work | encounter, tests, priority, note, state, timestamps, actors; result value and flag |
| Invoice (native) | Billing | patient, branch, appointment, lines with source, payments |
| Reminder | Outbound reminder | appointment, channel (email / SMS), scheduled time, state |
| Notification | In-app alert | user, title, body, kind, target screen/record, read, dedupe key |
| AI suggestion | AI audit trail | kind, user, output, status (generated / applied / dismissed) |

### Relationships

```
Branch ─< Department            Branch ─< Room            Branch ── Warehouse
Patient ─< Allergy / Condition / Contact / Document
Patient ─< Appointment >─ Provider (─ User)      Appointment ── Visit type ── Service product
Appointment ─ Queue ticket
Appointment ─ Encounter ─< Diagnosis
                       ─< Prescription ─< Line ── Product (stock, lots, expiry)
                       ─< Lab order ─< Result ── Parameter ── Test
Appointment ─< Invoice ─< Invoice line (consultation | lab order | prescription line) ─< Payment
Patient ── Portal user          Patient ─< Messages          Appointment ─< Reminder
User ─< Notification            User ─< Staff access log
```

---

## 11. Notifications and automation

### In-app notifications

| Event | Who is notified |
|---|---|
| Prescription issued | Pharmacists of the branch |
| Lab results released | Ordering doctor |
| New patient message | Reception of the branch |
| Portal booking request | Reception |
| Appointment rescheduled | The doctor |
| Low stock | Pharmacists |
| Invoice overdue | Finance |
| No-show rate rising in a department | Managers |

Duplicate notifications are suppressed with a dedupe key (for example "Low stock: Gloves" is sent once).

### Scheduled jobs

| Job | Frequency | Does |
|---|---|---|
| Send reminders | every 10 minutes | Emails due reminders; marks failures with the reason |
| Low-stock check | daily | Notifies pharmacists about items below reorder level |
| Overdue invoices | daily | Flags and notifies overdue balances |
| Operational insights | daily | Detects abnormal no-show rates |
| Complete courses | daily | Closes dispensed prescriptions whose course has ended |

---

## 12. AI assistance

| | |
|---|---|
| **Where** | "AI Assistant" drawer in the topbar |
| **What** | Summarise a patient; draft consultation notes; explain the reception day; explain the manager dashboard; explain an invoice |
| **Model** | Anthropic Claude through the official SDK, with structured (JSON-schema) output |
| **Default** | **Off.** An administrator enables it and enters an API key |

**Safeguards:**
- **De-identification:** names, patient IDs, phone numbers, emails and national IDs are removed, and
  free text is scrubbed, before anything is sent.
- **Assistive only:** every output is labelled **"AI-GENERATED · REQUIRES REVIEW"**. Nothing is written
  to the medical record until a clinician chooses which parts to apply.
- **Audit:** every request, apply and dismiss is stored with who did it.
- **Refusals and errors** are shown as such, never as made-up content.

---

## 13. Patient portal

- **URL:** `/careos/portal`. Patients sign in with their portal account (invited from Patient 360 →
  "Invite to portal"). Staff are redirected to the staff app.
- **Home:** greeting; next appointment with **Reschedule** and **Book new**; active prescriptions; new
  lab results; balance due.
- **Appointments:** upcoming and past visits and requests.
- **Prescriptions:** active and past medication with dose and instructions.
- **Lab results:** only **verified** results, with values, units, reference ranges and flags.
- **Billing:** invoices, status and balance, and **Pay now** through Odoo's secure payment page (needs a
  payment provider).
- **Messages:** two-way thread with the clinic.
- **Mobile-first layout.**
- **Staff preview:** "View as patient →" shows exactly what a patient sees, for support.
- **Isolation:** every portal request works out the patient from the logged-in account and never trusts
  a patient ID sent by the browser.

---

## 14. Design system

| Token group | Values |
|---|---|
| Brand colour | Deep teal (`oklch(47% 0.1 195)`), explicitly "not hospital blue" |
| Wordmark | Lowercase **care** + an **os** chip |
| Typography | Inter (UI), Encode Sans Expanded (wordmark) |
| Surfaces | Light app background, white cards, dark navy sidebar |
| Status colours | Success (green), warning (amber), danger (red), info (teal), neutral (grey) badges |
| Motion | Short, functional transitions |

- Tokens are CSS custom properties scoped to `.careos`. Components use `co-` classes with plain CSS.
- Components:
  - layout: page header, cards, metric tiles, tables (interactive, responsive column hiding), tabs,
    segmented controls;
  - status and people: badges, avatars, timeline;
  - overlays: modal, record picker, command palette;
  - states: empty, loading and error states.
- Accessibility: keyboard navigation for tables, dialogs and the palette; ARIA roles on tabs, menus and
  alerts; colour is never the only signal (badges carry text).
- Design source: the Claude Design project (MediFlow Spec, MediFlow Prototype, CareOS Brand & Design
  System).

---

## 15. Architecture

```
┌──────────────────────────── Browser ────────────────────────────┐
│  CareOS staff app (OWL, full screen)      Patient portal (OWL)  │
└───────────────┬─────────────────────────────────┬───────────────┘
                │ JSON-RPC (careos_* methods)     │ portal routes
┌───────────────▼─────────────────────────────────▼───────────────┐
│  Service layer (role check first, then scoped elevated access)  │
│  billing · inventory · analytics · staff · portal · ai · setup  │
├─────────────────────────────────────────────────────────────────┤
│  Domain models: patient · appointment · queue · encounter ·     │
│  diagnosis · prescription · lab order · reminder · notification │
├─────────────────────────────────────────────────────────────────┤
│  Odoo 19: ORM · security groups · record rules · mail/audit ·   │
│  accounting · stock (lots, expiry, FEFO) · portal · email       │
└─────────────────────────────────────────────────────────────────┘
                              PostgreSQL
```

**Key technical decisions**

- **Native objects.** Invoices, payments, credit notes, stock moves, lots and email are Odoo's own.
  CareOS adds healthcare fields and flows on top.
- **Extension points instead of hard dependencies.**
  - The shell exposes JavaScript registries:
    - screens and dashboards;
    - topbar items and sidebar actions;
    - Patient 360 tabs and overview cards;
    - reception panels, appointment sections and queue actions;
    - encounter sections and actions;
    - doctor dashboard panels.
  - Python hooks cover timeline events, workflow transitions, dashboard data, workspace data and search
    providers.
  - Higher modules plug into lower ones; lower modules never import higher ones.
- **Explicit public API.** Methods called from the browser are prefixed `careos_` and check permissions
  themselves.
- **Time.** "Today" and working hours are computed in the branch's timezone.
- **Tech stack:**
  - backend: Python 3.12, Odoo 19, PostgreSQL;
  - frontend: OWL components and plain CSS;
  - tests: Odoo test framework, freezegun and headless Chrome tours;
  - AI: `anthropic` SDK.

---

## 16. Modules

| Module | Depends on | Provides |
|---|---|---|
| `careos_base` | web, mail, auth_signup | Shell, design system, branches, departments, 8 roles, branch context, search, notifications, Staff & roles |
| `careos_patients` | careos_base | Patients, allergies, conditions, contacts, documents, notes, directory, Patient 360 |
| `careos_appointments` | careos_patients | Providers, rooms, visit types, booking and lifecycle, schedule, reception dashboard |
| `careos_queue` | careos_appointments | Queue tickets, live queue board |
| `careos_clinical` | careos_queue | Encounters, vitals, diagnoses, sign-off, doctor workspace, follow-ups |
| `careos_inventory` | careos_base, stock, product_expiry | Medicines and supplies, lots and expiry, receiving, low-stock alerts |
| `careos_prescriptions` | careos_clinical, careos_inventory | Prescribing, allergy warnings, dispensing, current medications |
| `careos_laboratory` | careos_clinical | Test catalogue, orders, worklist, verified results |
| `careos_finance` | careos_prescriptions, careos_laboratory, account | Visit billing, payments, refunds, overdue, invoices workspace |
| `careos_communications` | careos_appointments | Patient messages, inbox, reminders |
| `careos_analytics` | careos_finance | Manager dashboard, analytics, insights, demo history |
| `careos_ai` | careos_analytics (+ `anthropic`) | AI assistant, de-identification, audit |
| `careos_portal` | careos_communications, careos_finance, portal | Patient portal, staff preview, portal invitations |
| `careos` | careos_portal, careos_ai | Meta module: full suite and setup guide |

---

## 17. Security, privacy and compliance

- **Server-side enforcement:** access rules, record rules, field restrictions and workflow role checks
  (section 9).
- **Multi-company and multi-branch isolation:** staff see only their company and branches, doctors only
  their own schedule, patients only their own record.
- **Audit trail:**
  - identity and clinical changes are tracked with who, when, old and new value;
  - staff access changes are logged;
  - AI activity is logged.
- **No destructive deletes:** patients and allergies are archived or retired, not deleted.
- **Passwords:** set only by their owner through the invitation link.
- **Attachments:** only people who can read the patient can download their documents.
- **AI privacy:** de-identified context, human review and opt-in (section 12).
- **Secrets:** configuration (database password, master password, API keys) stays in `odoo.conf`, which
  is not committed.
- **Compliance notes (Egypt):** the Personal Data Protection Law (Law 151 of 2020) treats health data as
  sensitive. A production deployment needs:
  - HTTPS;
  - access control and backups;
  - a data-processing basis and patient consent;
  - retention rules.

  CareOS provides the access control and audit pieces; hosting, backups and policy are deployment tasks.

---

## 18. Installation and operations

### Requirements

- Python 3.12, PostgreSQL 14+ (developed on 18), Odoo 19.0 source.
- Python packages: Odoo's `requirements.txt`, plus `anthropic` (AI), `freezegun` (tests) and
  `websocket-client` (browser tests).
- An outgoing mail server (invitations, reminders, patient replies).
- Optional: an Odoo payment provider (online payment), an SMS provider (SMS reminders), an Anthropic API
  key (AI).

### Install

```bash
git clone https://github.com/real-GBOY/clinicOS.git && cd clinicOS
git clone --depth 1 --branch 19.0 https://github.com/odoo/odoo.git odoo
python -m venv .venv && . .venv/Scripts/activate      # or: source .venv/bin/activate
pip install -r odoo/requirements.txt anthropic freezegun websocket-client
cp odoo.conf.example odoo.conf                          # set addons_path, data_dir, admin_passwd
```

**Real clinic (empty database, local chart of accounts and currency):**
```bash
python odoo/odoo-bin -c odoo.conf -d careos -i careos_base --stop-after-init
# set the company's country and currency (e.g. Egypt / EGP), then:
python odoo/odoo-bin -c odoo.conf -d careos -i careos --stop-after-init
python odoo/odoo-bin -c odoo.conf -d careos
```

Then sign in as administrator, complete the **Setup guide** and invite staff from **Staff & roles**.

**Demo database:**
```bash
python odoo/odoo-bin -c odoo.conf -d careos_demo --with-demo -i careos --stop-after-init
```

### Production checklist

- Linux server, Odoo with multiple worker processes behind a reverse proxy (nginx) with **HTTPS**.
- A strong master password; database manager disabled or restricted.
- **Automated daily backups** (database and filestore), tested restores.
- Outgoing mail configured (SPF/DKIM for the clinic's domain).
- Payment provider for online payment; SMS provider when available.
- Monitoring of disk space, memory and error logs.

---

## 19. Demo and showcase data

**Demo accounts** (demo databases only; password = login):

| Login | Role | Name |
|---|---|---|
| reception | Reception | Salma Adel |
| doctor | Doctor (Cardiology) | Dr. Nourhan Saeed |
| doctor2 | Doctor (Internal Medicine) | Dr. Karim Fathy |
| nurse | Nurse | Hoda Mansour |
| lab | Laboratory | Tamer Lotfy |
| pharmacist | Pharmacy | Mariam Farid |
| finance | Finance | Youssef Samir |
| manager | Manager | Rana Aziz |
| admin | Administrator | Mitchell Admin |
| patient | Patient portal | Ahmed Hassan → `/careos/portal` |

- **Standard demo:** a Cairo clinic with today's schedule, a live queue, 8 weeks of visit history with
  invoices, prescriptions, lab work, stock and patient messages. The schedule is generated relative to
  the install date.
- **Showcase database** (`careos_showcase`, used for marketing screenshots):
  - "Nile Care Clinics", in EGP;
  - 81 patients, 1,530 appointments, 944 consultations, about 1,900 invoices;
  - a live clinic day with every state represented.

  Its screenshots are in the `showcase/` folder. All people and records are synthetic.

---

## 20. Quality and testing

- **180 automated tests**, all passing on a fresh database.
- **Browser tours (headless Chrome):**
  - patient registration;
  - booking from Patient 360;
  - a full reception day (check-in → queue → consultation → completion);
  - a full doctor visit (vitals, notes, diagnosis, prescription, lab order, sign-off);
  - the patient portal (message, booking request);
  - staff administration (invite, add role, deactivate).
- **What the tests prove:**
  - every state machine transition, allowed and refused, per role;
  - branch and company isolation, doctor own-schedule rules, portal isolation;
  - booking conflicts, working-day rules, ticket numbering, check-in atomicity;
  - vitals ranges, sign-off rules, allergy warnings, stock consumption and shortages;
  - invoice lines, payments, refunds, statuses, overdue detection;
  - notifications and deduplication, reminder scheduling and failure handling;
  - AI disabled by default, de-identification, review-before-apply, audit (model calls mocked);
  - staff safeguards (self-protection, last administrator, audit log not writable).
- Date-dependent tests run on a frozen clock.

```bash
python odoo/odoo-bin -c odoo.conf -d careos_ci --with-demo -i careos --test-enable \
  --test-tags /careos_base,/careos_patients,/careos_appointments,/careos_queue,/careos_clinical,/careos_inventory,/careos_prescriptions,/careos_laboratory,/careos_finance,/careos_communications,/careos_analytics,/careos_ai,/careos_portal,/careos \
  --http-port 8079 --stop-after-init --log-level=test
```

---

## 21. Known limitations

| Area | Limitation |
|---|---|
| Language | English only. Arabic and right-to-left layout are not done yet |
| SMS | No SMS provider connected; email reminders work |
| Online payment | "Pay now" needs an Odoo payment provider configured |
| Refreshing | Queue, dashboards and notifications refresh on a timer, not by push |
| Timezones | Times display in the browser's timezone; staff machines should use the branch timezone |
| Schedules | Branch opening hours only; no per-doctor rotas, leave or breaks |
| Admin screens | Rooms, visit types and providers still use standard Odoo forms after the setup guide |
| Doctor ↔ account link | Done in the setup guide or provider settings, not yet in Staff & roles |
| Field visibility | National ID and insurance are visible to all staff roles |
| Read audit | Changes are audited; record *views* are not logged yet |
| Insurance | Insurance details are stored; claims and approvals are not managed |
| Demo currency | In demo databases Odoo's accounting demo switches the company to USD (real databases use your currency) |
| Branding | The login page is Odoo-branded; fonts load from Google Fonts |

---

## 22. Roadmap

**Now: foundation for real clinics**
1. Continuous integration: run the full test suite on every push.
2. **Arabic with right-to-left layout** across the staff app and the portal.
3. **Egyptian payments** (Paymob / Fawry) for "Pay now"; **SMS / WhatsApp reminders** through a local
   provider.
4. Production deployment: Linux, HTTPS, workers, automated backups, monitoring.

**Next: pilot learnings**
5. Pilot with one clinic for 2–4 weeks and prioritise from real usage.
6. Push updates instead of timer refresh (Odoo bus) for the queue, dashboards and notifications.
7. Per-doctor schedules: rotas, leave, breaks, slot templates.
8. A read-access audit log, and field-level restriction of national ID and insurance.
9. CareOS screens for rooms, visit types and providers; doctor-to-account linking in Staff & roles.

**Later: growth**
10. Insurance claims and pre-approvals.
11. Doctor fees and commissions.
12. Pharmacy counter sales and supplier purchase orders.
13. Imaging / radiology orders.
14. Patient mobile app on top of the portal.
15. Standards-based integrations (HL7 FHIR, LOINC codes for lab tests).

---

## 23. Glossary

| Term | Meaning |
|---|---|
| **Encounter** | The clinical record of one consultation (vitals, notes, diagnoses, orders) |
| **Queue ticket** | The numbered place of a checked-in patient in today's queue |
| **Sign-off** | The doctor closing the encounter; the record becomes read-only |
| **Issue (prescription)** | Finalise a prescription so the pharmacy can dispense it |
| **Dispense** | Pharmacy hands over the medication; stock is consumed |
| **FEFO** | First-expiry-first-out: the batch expiring soonest is used first |
| **Verify (lab)** | The lab's technical validation of results before release |
| **Review (lab)** | The ordering doctor acknowledging released results |
| **Patient 360** | The single page with everything about one patient |
| **Branch** | A clinic location with its own hours, rooms, stock and staff |
| **Provider** | A doctor who can be booked |
| **Visit type** | A kind of appointment (new patient, follow-up, consultation) with duration and price |
| **No-show** | A patient who did not attend a confirmed appointment |
| **Utilisation** | Booked time as a share of opening hours |
| **Portal** | The patient-facing website at `/careos/portal` |

---

*CareOS: built on Odoo 19. All patient and staff data in demos, screenshots and this document is synthetic.*
