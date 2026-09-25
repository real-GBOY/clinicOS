# Testing

All CareOS tests are tagged `careos` and run post-install.

```bash
# Git Bash: MSYS_NO_PATHCONV=1 stops "/careos_base" being rewritten as a Windows path
MSYS_NO_PATHCONV=1 .venv/Scripts/python.exe odoo/odoo-bin -c odoo.conf -d careos_test \
  -i careos_patients --test-enable --test-tags /careos_base,/careos_patients \
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

## Notes

* Mail tracking is finalized in `cr.precommit`; fixtures run it once so later edits are tracked as updates
  (see `tests/common.py`).
* The tour sets native date inputs via DOM events; the tour `edit` helper cannot drive them.
