# Known issues and deferred work

Recorded deliberately so they do not derail vertical slices. None blocks the current workflows.

## From slice 1 (foundation, patients)

| Item | Notes |
|---|---|
| Odoo navbar can flash during the very first load | Hidden as soon as the CareOS shell mounts; a fullscreen-at-boot web client patch would remove it entirely |
| Odoo-branded login page | Needs a CareOS login template |
| Admin configuration uses standard Odoo list/form views | Branches, departments, providers, rooms, visit types — until a CareOS settings workspace exists |
| Fonts loaded from Google Fonts | Bundle locally for offline and privacy-sensitive deployments |
| Selects have no custom caret | Native select styling |
| No CareOS date-picker component | Native date input |
| National ID and insurance visible to every role | Field-level restriction per role not yet decided |
| No record-view audit log | Mail tracking covers writes only |

## From slice 2 (appointments, queue, reception dashboard)

| Item | Notes |
|---|---|
| Browser vs branch timezone | The server defines "today" in the branch timezone; the UI renders times in the browser timezone. Correct when staff browsers are set to the branch timezone (the normal case); mixed-timezone setups would see shifted times |
| No provider working hours / rotas | Booking prevents conflicts and shows busy slots (07:00–21:00, 15-minute grid) but does not know when a provider is off |
| Queue and dashboard refresh by polling | 15 s (queue) / 30 s (dashboard); switch to the Odoo bus for push updates |
| Reception can start/complete consultations | Operational only while no clinical record exists; restrict to clinicians when `careos_clinical` creates encounters |
| Doctors have no workspace yet | They land on Patients; the prototype's Doctor Workspace comes with the clinical slice |
| Week view of the schedule | Day view only |
| Demo schedule is relative to the install date | Re-seed with `_careos_demo_schedule()` / `_careos_demo_queue()` (see development.md) |
| Walk-in patients | A walk-in is booked for "now" and checked in; no dedicated walk-in shortcut yet |
