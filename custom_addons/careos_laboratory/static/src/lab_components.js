import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { CareModal } from "@careos_base/components/modal";
import { formatDisplayDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { encounterActionRegistry, encounterSectionRegistry, doctorPanelRegistry } from "@careos_clinical/clinical_registries";
import { patientTabRegistry } from "@careos_patients/screens/patient_360";

export const LAB_TONE = {
    ordered: "neutral",
    collected: "neutral",
    processing: "warning",
    result_entered: "info",
    verified: "success",
    completed: "success",
};
const ACTIONS = {
    collect: { label: "Mark sample collected", method: "action_collect", style: "primary" },
    process: { label: "Start processing", method: "action_process", style: "primary" },
    verify: { label: "Mark verified", method: "action_verify", style: "primary" },
    review: { label: "Mark reviewed", method: "action_review", style: "success" },
};
const FLAG_CLASS = { high: "co-result--high", low: "co-result--low", normal: "" };

/** Result rows with abnormal highlighting (shared by worklist, encounter, patient). */
export class LabResults extends Component {
    static template = "careos_laboratory.LabResults";
    static props = { order: Object, editable: { type: Boolean, optional: true }, values: { type: Object, optional: true } };

    flagClass(result) {
        return FLAG_CLASS[result.flag] || "";
    }
}

/** Order lab tests from the encounter. */
export class LabOrderDialog extends Component {
    static template = "careos_laboratory.LabOrderDialog";
    static components = { CareModal };
    static props = { close: Function, encounterId: Number, onDone: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ tests: [], selected: new Set(), priority: "routine", note: "", error: "", saving: false });
        onWillStart(async () => {
            this.state.tests = await this.orm.call("careos.lab.order", "careos_catalogue", []);
        });
    }

    toggle(test) {
        const selected = this.state.selected;
        selected.has(test.id) ? selected.delete(test.id) : selected.add(test.id);
    }

    async save() {
        if (!this.state.selected.size) {
            this.state.error = "Choose at least one test.";
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("careos.encounter", "careos_order_lab", [[this.props.encounterId], [...this.state.selected]], {
                priority: this.state.priority,
                note: this.state.note,
            });
            await this.props.onDone();
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || "The order could not be placed.";
        } finally {
            this.state.saving = false;
        }
    }
}

export class EncounterLabOrders extends Component {
    static template = "careos_laboratory.EncounterLabOrders";
    static components = { Badge, LabResults };
    static props = { encounter: Object, reload: Function };

    tone(order) {
        return LAB_TONE[order.state];
    }

    open(order) {
        this.env.careos.navigate("lab", { resId: order.id });
    }
}

encounterSectionRegistry.add("lab", { sequence: 20, Component: EncounterLabOrders });
encounterActionRegistry.add("lab_order", {
    label: "+ Lab order",
    sequence: 20,
    isVisible: (encounter) => encounter.can_order_lab,
    run: (encounter, env, reload) => env.services.dialog.add(LabOrderDialog, { encounterId: encounter.id, onDone: reload }),
});

/** Prototype "Laboratory Worklist": orders on the left, the selected order on the right. */
export class LabWorklist extends Component {
    static template = "careos_laboratory.LabWorklist";
    static components = { Badge, EmptyState, LabResults, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ scope: "active", rows: null, selected: null, values: {}, error: "", busy: false });
        onWillStart(async () => {
            await this.load();
            const id = this.props.params?.resId || this.state.rows?.[0]?.id;
            if (id) {
                await this.select(id);
            }
        });
    }

    async load() {
        try {
            this.state.rows = await this.orm.call("careos.lab.order", "careos_worklist", [], { scope: this.state.scope });
        } catch (error) {
            this.state.error = error.data?.message || "The worklist could not be loaded.";
        }
    }

    async setScope(scope) {
        this.state.scope = scope;
        await this.load();
    }

    async select(id) {
        const order = await this.orm.call("careos.lab.order", "careos_get_detail", [[id]]);
        this.state.selected = order;
        this.state.values = Object.fromEntries(order.results.map((r) => [String(r.id), r.value === "" ? "" : String(r.value)]));
    }

    tone(order) {
        return LAB_TONE[order.state];
    }

    get actions() {
        return (this.state.selected?.actions || []).filter((a) => a !== "enter_results").map((key) => ({ key, ...ACTIONS[key] }));
    }

    date(order) {
        return formatDisplayDate(order.ordered_at);
    }

    async run(action) {
        await this.guard(() => this.orm.call("careos.lab.order", ACTIONS[action].method, [[this.state.selected.id]]));
    }

    async saveResults() {
        await this.guard(() => this.orm.call("careos.lab.order", "careos_save_results", [[this.state.selected.id], this.state.values]),
            "Results saved.");
    }

    async submitResults() {
        await this.guard(() => this.orm.call("careos.lab.order", "action_submit_results", [[this.state.selected.id], this.state.values]),
            "Results released to the ordering doctor.");
    }

    async guard(call, message) {
        this.state.busy = true;
        try {
            await call();
            if (message) {
                this.notification.add(message, { type: "success" });
            }
            await Promise.all([this.load(), this.select(this.state.selected.id)]);
        } catch (error) {
            this.notification.add(error.data?.message || "The order could not be updated.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openPatient() {
        this.env.careos.navigate("patient", { resId: this.state.selected.patient.id });
    }
}

/** Doctor Workspace → Pending lab results. */
export class PendingLabPanel extends Component {
    static template = "careos_laboratory.PendingLabPanel";
    static props = { dashboard: Object, reload: Function };

    get orders() {
        return this.props.dashboard.panels?.lab || [];
    }

    color(order) {
        return `co-lab-status--${LAB_TONE[order.state]}`;
    }

    open(order) {
        this.env.careos.navigate("lab", { resId: order.id });
    }
}
doctorPanelRegistry.add("lab", { sequence: 10, Component: PendingLabPanel });

/** Patient 360 → Laboratory. */
export class PatientLab extends Component {
    static template = "careos_laboratory.PatientLab";
    static components = { Badge, EmptyState, LabResults, LoadingState };
    static props = { profile: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ orders: null, error: "" });
        onWillStart(async () => {
            try {
                this.state.orders = await this.orm.call("careos.patient", "careos_get_lab_results", [[this.props.profile.id]]);
            } catch (error) {
                this.state.error = error.data?.message || "Lab results could not be loaded.";
            }
        });
    }

    tone(order) {
        return LAB_TONE[order.state];
    }

    date(order) {
        return formatDisplayDate(order.ordered_at);
    }
}
patientTabRegistry.add("lab", {
    label: "Laboratory",
    sequence: 18,
    Component: PatientLab,
    isVisible: (profile) => profile.lab_access,
});

screenRegistry.add("lab", {
    label: "Laboratory",
    navGroup: "clinical",
    sequence: 40,
    roles: ["lab", "doctor", "nurse"],
    Component: LabWorklist,
});
