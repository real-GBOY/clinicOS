import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, Timeline } from "@careos_base/components/primitives";
import { RecordEntryDialog } from "@careos_base/components/record_entry_dialog";
import { formatDisplayDate, formatShortDate } from "@careos_base/components/format";
import { patientTabRegistry } from "../screens/patient_360";

const SEVERITY_TONE = { mild: "warning", moderate: "danger", severe: "danger" };
const CONDITION_TONE = { active: "warning", controlled: "info", resolved: "success" };

export class PatientOverview extends Component {
    static template = "careos_patients.PatientOverview";
    static components = { Badge, EmptyState, Timeline };
    static props = { profile: Object, reload: Function };

    setup() {
        this.dialog = useService("dialog");
    }

    get p() {
        return this.props.profile;
    }

    get identityRows() {
        const p = this.p;
        return [
            ["Patient ID", p.ref],
            ["Date of birth", p.date_of_birth ? `${formatDisplayDate(p.date_of_birth)} (${p.age}y)` : "—"],
            ["National ID", p.national_id || "—"],
            ["Phone", p.phone || "—"],
            ["Email", p.email || "—"],
            ["Address", p.address || "—"],
            ["Home branch", p.branch ? p.branch.name : "—"],
            ["Insurance", p.insurance_provider ? `${p.insurance_provider} · ${p.insurance_policy_number || "no policy #"}` : "Self-pay"],
            ["Registered", formatDisplayDate(p.registered_on)],
        ];
    }

    get timelineEvents() {
        return this.p.timeline.map((e) => ({ ...e, date: formatShortDate(e.date) }));
    }

    severityTone(allergy) {
        return SEVERITY_TONE[allergy.severity] || "neutral";
    }

    conditionTone(condition) {
        return CONDITION_TONE[condition.status] || "neutral";
    }

    formatDate(value) {
        return formatDisplayDate(value);
    }

    addAllergy() {
        this.dialog.add(RecordEntryDialog, {
            title: "Record allergy",
            model: "careos.patient.allergy",
            defaults: { patient_id: this.p.id },
            fields: [
                { name: "allergen", label: "Allergen", type: "char", required: true, wide: true, placeholder: "e.g. Penicillin" },
                { name: "severity", label: "Severity", type: "select", required: true, default: "moderate",
                  options: [["mild", "Mild"], ["moderate", "Moderate"], ["severe", "Severe"]] },
                { name: "reaction", label: "Reaction", type: "char", placeholder: "e.g. Hives" },
            ],
            onSaved: () => this.props.reload(),
        });
    }

    addCondition() {
        this.dialog.add(RecordEntryDialog, {
            title: "Add condition",
            model: "careos.patient.condition",
            defaults: { patient_id: this.p.id },
            fields: [
                { name: "name", label: "Condition", type: "char", required: true, wide: true },
                { name: "code", label: "Code (ICD-10)", type: "char", placeholder: "e.g. I10" },
                { name: "status", label: "Status", type: "select", required: true, default: "active",
                  options: [["active", "Active"], ["controlled", "Controlled"], ["resolved", "Resolved"]] },
                { name: "onset_date", label: "Onset", type: "date" },
            ],
            onSaved: () => this.props.reload(),
        });
    }

    addContact() {
        this.dialog.add(RecordEntryDialog, {
            title: "Add contact",
            model: "careos.patient.contact",
            defaults: { patient_id: this.p.id },
            fields: [
                { name: "name", label: "Name", type: "char", required: true },
                { name: "relationship", label: "Relationship", type: "select", required: true, default: "spouse",
                  options: [["spouse", "Spouse"], ["parent", "Parent"], ["child", "Child"], ["sibling", "Sibling"], ["guardian", "Guardian"], ["other", "Other"]] },
                { name: "phone", label: "Phone", type: "char", required: true },
                { name: "is_emergency", label: "Emergency contact", type: "boolean", default: true },
            ],
            onSaved: () => this.props.reload(),
        });
    }
}

patientTabRegistry.add("overview", {
    label: "Overview",
    sequence: 1,
    Component: PatientOverview,
});
