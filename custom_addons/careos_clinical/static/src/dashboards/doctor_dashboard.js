import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { dashboardRegistry } from "@careos_base/shell/screen_registry";
import { APPOINTMENT_TONE, formatTime } from "@careos_appointments/appointment_utils";
import { doctorPanelRegistry } from "../clinical_registries";

const REFRESH_MS = 30000;

/** Prototype "Doctor Workspace": today's schedule, pending results, follow-ups. */
export class DoctorDashboard extends Component {
    static template = "careos_clinical.DoctorDashboard";
    static components = { Badge, EmptyState, LoadingState, PageHeader };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ d: null, error: "" });
        onWillStart(() => this.load());
        const interval = setInterval(() => this.load(), REFRESH_MS);
        onWillUnmount(() => clearInterval(interval));
    }

    async load() {
        try {
            this.state.d = await this.orm.call("careos.appointment", "careos_doctor_dashboard", []);
            this.state.error = "";
        } catch (error) {
            this.state.error = error.data?.message || "The workspace could not be loaded.";
        }
    }

    get d() {
        return this.state.d;
    }

    get subtitle() {
        return [this.d.provider, this.d.department].filter(Boolean).join(" · ");
    }

    get panels() {
        return doctorPanelRegistry
            .getEntries()
            .map(([id, panel]) => ({ id, ...panel }))
            .sort((a, b) => (a.sequence ?? 10) - (b.sequence ?? 10));
    }

    tone(appt) {
        return APPOINTMENT_TONE[appt.state];
    }

    time(appt) {
        return formatTime(appt.start);
    }

    due(value) {
        return formatDisplayDate(value);
    }

    open(appt) {
        if (appt.encounter_id) {
            this.env.careos.navigate("encounter", { resId: appt.encounter_id });
        } else {
            this.env.careos.navigate("appointment", { resId: appt.id });
        }
    }

    openEncounter(row) {
        this.env.careos.navigate("encounter", { resId: row.id });
    }

    openPatient(row) {
        this.env.careos.navigate("patient", { resId: row.patient.id });
    }
}

dashboardRegistry.add("doctor", {
    label: "Doctor",
    sequence: 20,
    roles: ["doctor"],
    defaultFor: ["doctor"],
    Component: DoctorDashboard,
});
