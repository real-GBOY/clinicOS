import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CareModal } from "@careos_base/components/modal";
import { formatDisplayDate } from "@careos_base/components/format";

const FIELDS = [
    "name",
    "date_of_birth",
    "sex",
    "phone",
    "email",
    "national_id",
    "street",
    "city",
    "branch_id",
    "insurance_provider",
    "insurance_policy_number",
];

/**
 * Register a new patient or edit an existing one. Before saving a new patient
 * the dialog checks for likely duplicates (same national ID, phone or name) and
 * asks the receptionist to confirm — the spec's "dedupe-check" step.
 */
export class PatientFormDialog extends Component {
    static template = "careos_patients.PatientFormDialog";
    static components = { CareModal };
    static props = {
        close: Function,
        patient: { type: Object, optional: true }, // profile payload when editing
        branches: Array,
        defaultBranchId: { type: [Number, Boolean], optional: true },
        onSaved: Function,
        onOpenExisting: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        const p = this.props.patient;
        this.state = useState({
            values: {
                name: p?.name || "",
                date_of_birth: p?.date_of_birth || "",
                sex: p?.sex || "",
                phone: p?.phone || "",
                email: p?.email || "",
                national_id: p?.national_id || "",
                street: p?.street || "",
                city: p?.city || "",
                branch_id: String(p?.branch?.id || this.props.defaultBranchId || ""),
                insurance_provider: p?.insurance_provider || "",
                insurance_policy_number: p?.insurance_policy_number || "",
            },
            errors: {},
            serverError: "",
            duplicates: [],
            duplicatesAcknowledged: false,
            saving: false,
        });
        this.today = luxon.DateTime.now().toISODate();
    }

    get isEdit() {
        return Boolean(this.props.patient);
    }

    get title() {
        return this.isEdit ? `Edit ${this.props.patient.name}` : "Register patient";
    }

    formatDate(value) {
        return formatDisplayDate(value);
    }

    validate() {
        const v = this.state.values;
        const errors = {};
        if (!v.name.trim()) {
            errors.name = "Full name is required";
        }
        if (v.date_of_birth && v.date_of_birth > this.today) {
            errors.date_of_birth = "Date of birth cannot be in the future";
        }
        if (v.phone && v.phone.replace(/\D/g, "").length < 7) {
            errors.phone = "Enter a valid phone number";
        }
        if (v.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.email)) {
            errors.email = "Enter a valid email address";
        }
        this.state.errors = errors;
        return !Object.keys(errors).length;
    }

    onIdentityChange() {
        // Any change to identifying fields invalidates a previous confirmation.
        this.state.duplicatesAcknowledged = false;
        this.state.duplicates = [];
    }

    async checkDuplicates() {
        const v = this.state.values;
        return this.orm.call("careos.patient", "careos_find_duplicates", [], {
            name: v.name,
            phone: v.phone,
            national_id: v.national_id,
            exclude_id: this.props.patient?.id || false,
        });
    }

    buildVals() {
        const vals = {};
        for (const field of FIELDS) {
            const value = this.state.values[field];
            if (field === "branch_id") {
                vals[field] = value ? parseInt(value) : false;
            } else {
                vals[field] = value === "" ? false : value;
            }
        }
        return vals;
    }

    async save() {
        if (this.state.saving || !this.validate()) {
            return;
        }
        this.state.saving = true;
        this.state.serverError = "";
        try {
            if (!this.isEdit && !this.state.duplicatesAcknowledged) {
                const duplicates = await this.checkDuplicates();
                if (duplicates.length) {
                    this.state.duplicates = duplicates;
                    this.state.duplicatesAcknowledged = true;
                    return;
                }
            }
            const vals = this.buildVals();
            let id = this.props.patient?.id;
            if (id) {
                await this.orm.write("careos.patient", [id], vals);
            } else {
                [id] = await this.orm.create("careos.patient", [vals]);
            }
            await this.props.onSaved(id);
            this.props.close();
        } catch (error) {
            this.state.serverError = error.data?.message || "The patient could not be saved.";
        } finally {
            this.state.saving = false;
        }
    }

    openExisting(duplicate) {
        this.props.close();
        this.props.onOpenExisting?.(duplicate.id);
    }

    get submitLabel() {
        if (this.isEdit) {
            return "Save changes";
        }
        return this.state.duplicates.length ? "Register anyway" : "Register patient";
    }
}
