import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { formatTime } from "@careos_appointments/appointment_utils";
import { encounterActionRegistry, encounterSectionRegistry } from "@careos_clinical/clinical_registries";
import { patientOverviewCardRegistry } from "@careos_patients/tabs/patient_overview";

export const RX_TONE = { draft: "neutral", issued: "info", dispensed: "success", completed: "success", cancelled: "danger" };
const ACTION_META = {
    issue: { label: "Issue prescription", style: "primary", method: "action_issue" },
    dispense: { label: "Dispense", style: "success", method: "action_dispense" },
    complete: { label: "Mark course completed", style: "secondary", method: "action_complete" },
    cancel: { label: "Cancel", style: "ghost", method: "action_cancel" },
};

/** Shared: workflow buttons for one prescription (server decides which). */
export class PrescriptionActions extends Component {
    static template = "careos_prescriptions.PrescriptionActions";
    static props = { rx: Object, onChanged: Function, small: { type: Boolean, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ busy: false });
    }

    get actions() {
        return this.props.rx.actions.map((key) => ({ key, ...ACTION_META[key] }));
    }

    async run(action, ev) {
        ev?.stopPropagation();
        this.state.busy = true;
        try {
            await this.orm.call("careos.prescription", ACTION_META[action].method, [[this.props.rx.id]]);
            if (action === "dispense") {
                this.notification.add(`${this.props.rx.name} dispensed; stock updated.`, { type: "success" });
            }
            await this.props.onChanged();
        } catch (error) {
            this.notification.add(error.data?.message || "The prescription could not be updated.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

/** Encounter section: write and issue the prescription without leaving the consultation. */
export class EncounterPrescriptions extends Component {
    static template = "careos_prescriptions.EncounterPrescriptions";
    static components = { Badge, PrescriptionActions };
    static props = { encounter: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ meds: [], line: this.emptyLine() });
        onWillStart(async () => {
            if (this.props.encounter.can_prescribe) {
                this.state.meds = await this.orm.call("careos.prescription", "careos_medications", []);
            }
        });
    }

    emptyLine() {
        return { product_id: "", dose: "", frequency: "Once daily", duration_days: 30, quantity: 1, instructions: "" };
    }

    get prescriptions() {
        return this.props.encounter.prescriptions || [];
    }

    tone(rx) {
        return RX_TONE[rx.state];
    }

    onMedChange(ev) {
        this.state.line.product_id = ev.target.value;
        const med = this.state.meds.find((m) => String(m.id) === ev.target.value);
        if (med && !this.state.line.dose) {
            this.state.line.dose = med.strength;
        }
    }

    async addLine(rx) {
        const line = this.state.line;
        if (!line.product_id || !line.dose || !line.frequency) {
            this.notification.add("Choose a medication and enter dose and frequency.", { type: "warning" });
            return;
        }
        try {
            await this.orm.create("careos.prescription.line", [{
                prescription_id: rx.id,
                product_id: parseInt(line.product_id),
                dose: line.dose,
                frequency: line.frequency,
                duration_days: parseInt(line.duration_days),
                quantity: parseFloat(line.quantity),
                instructions: line.instructions,
            }]);
            this.state.line = this.emptyLine();
            await this.props.reload();
        } catch (error) {
            this.notification.add(error.data?.message || "The medication could not be added.", { type: "danger" });
        }
    }

    async removeLine(line) {
        await this.orm.unlink("careos.prescription.line", [line.id]);
        await this.props.reload();
    }
}

encounterSectionRegistry.add("prescriptions", { sequence: 10, Component: EncounterPrescriptions });

encounterActionRegistry.add("prescription", {
    label: "+ Prescription",
    sequence: 10,
    isVisible: (encounter) => encounter.can_prescribe,
    run: async (encounter, env, reload) => {
        await env.services.orm.call("careos.encounter", "careos_new_prescription", [[encounter.id]]);
        await reload();
        document.querySelector(".co-encounter-rx")?.scrollIntoView({ behavior: "smooth" });
    },
});

/** Prescriptions list — the pharmacy dispensing queue by default. */
export class PrescriptionList extends Component {
    static template = "careos_prescriptions.PrescriptionList";
    static components = { Badge, EmptyState, LoadingState, PageHeader, PrescriptionActions };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        const isPharmacy = this.env.careos.session.roles.includes("pharmacy");
        this.filters = [["issued", "To dispense"], ["dispensed", "Dispensed"], ["draft", "Draft"], ["", "All"]];
        this.state = useState({ state: isPharmacy ? "issued" : "", rows: null, error: "" });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.rows = await this.orm.call("careos.prescription", "careos_list", [], { state: this.state.state || false });
        } catch (error) {
            this.state.error = error.data?.message || "Prescriptions could not be loaded.";
        }
    }

    setFilter(value) {
        this.state.state = value;
        this.load();
    }

    meds(rx) {
        return rx.lines.map((l) => `${l.med.split(" (")[0]}`).join(", ") || "—";
    }

    tone(rx) {
        return RX_TONE[rx.state];
    }

    open(rx) {
        this.env.careos.navigate("prescription", { resId: rx.id });
    }
}

/** Prototype "Prescription — Ahmed Hassan". */
export class PrescriptionDetail extends Component {
    static template = "careos_prescriptions.PrescriptionDetail";
    static components = { Badge, EmptyState, LoadingState, PrescriptionActions };
    static props = { params: Object };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ rx: null, error: "" });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.rx = await this.orm.call("careos.prescription", "careos_get_detail", [[this.props.params.resId]]);
            this.env.careos.setPageTitle(`${this.state.rx.name} · ${this.state.rx.patient.name}`);
        } catch (error) {
            this.state.error = error.data?.message || "This prescription could not be opened.";
        }
    }

    get subtitle() {
        const rx = this.state.rx;
        return `Encounter ${formatDisplayDate(rx.encounter.date)}, ${formatTime(rx.encounter.date)} · ${rx.provider.name}`;
    }

    lineTone(line) {
        return RX_TONE[line.state];
    }

    openPatient() {
        this.env.careos.navigate("patient", { resId: this.state.rx.patient.id });
    }
}

/** Patient 360 overview: current medications (issued or dispensed). */
export class CurrentMedicationsCard extends Component {
    static template = "careos_prescriptions.CurrentMedicationsCard";
    static components = { Badge };
    static props = { profile: Object, reload: Function };

    tone(line) {
        return RX_TONE[line.state];
    }
}

screenRegistry.add("prescriptions", {
    label: "Prescriptions",
    navGroup: "clinical",
    sequence: 30,
    roles: ["doctor", "pharmacy", "nurse"],
    Component: PrescriptionList,
});
screenRegistry.add("prescription", {
    label: "Prescription",
    parent: "prescriptions",
    roles: ["doctor", "pharmacy", "nurse"],
    Component: PrescriptionDetail,
});
patientOverviewCardRegistry.add("current_medications", {
    sequence: 5,
    Component: CurrentMedicationsCard,
    isVisible: (profile) => profile.medications_access,
});
