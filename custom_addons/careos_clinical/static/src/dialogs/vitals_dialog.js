import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CareModal } from "@careos_base/components/modal";

const FIELDS = [
    { name: "bp_systolic", label: "Systolic BP", unit: "mmHg", step: 1 },
    { name: "bp_diastolic", label: "Diastolic BP", unit: "mmHg", step: 1 },
    { name: "heart_rate", label: "Heart rate", unit: "bpm", step: 1 },
    { name: "temperature", label: "Temperature", unit: "°C", step: 0.1 },
    { name: "spo2", label: "SpO2", unit: "%", step: 1 },
    { name: "respiratory_rate", label: "Respiratory rate", unit: "/min", step: 1 },
    { name: "weight", label: "Weight", unit: "kg", step: 0.1 },
    { name: "height", label: "Height", unit: "cm", step: 0.1 },
];

/** Record vitals on an encounter (nurse or doctor). Ranges are validated on the server. */
export class VitalsDialog extends Component {
    static template = "careos_clinical.VitalsDialog";
    static components = { CareModal };
    static props = { close: Function, encounterId: Number, patientName: String, onSaved: Function };

    setup() {
        this.orm = useService("orm");
        this.fields = FIELDS;
        this.state = useState({ values: {}, loading: true, error: "", saving: false });
        this.load();
    }

    async load() {
        const workspace = await this.orm.call("careos.encounter", "careos_get_workspace", [[this.props.encounterId]]);
        const values = {};
        for (const field of FIELDS) {
            values[field.name] = workspace.vitals_raw[field.name] || "";
        }
        Object.assign(this.state, { values, loading: false });
    }

    async save() {
        this.state.saving = true;
        this.state.error = "";
        const vals = {};
        for (const field of FIELDS) {
            const raw = this.state.values[field.name];
            vals[field.name] = raw === "" || raw === null ? false : Number(raw);
        }
        try {
            await this.orm.call("careos.encounter", "careos_save", [[this.props.encounterId], vals]);
            await this.props.onSaved();
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || "Vitals could not be saved.";
        } finally {
            this.state.saving = false;
        }
    }
}
