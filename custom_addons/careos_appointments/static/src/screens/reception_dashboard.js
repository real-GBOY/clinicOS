import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { PatientFormDialog } from "@careos_patients/dialogs/patient_form_dialog";
import { AppointmentActions } from "../components/appointment_actions";
import { BookingDialog } from "../dialogs/booking_dialog";
import { APPOINTMENT_TONE, formatTime } from "../appointment_utils";

const { DateTime } = luxon;

/** Side panels contributed by other modules (e.g. the live queue).
 * Entry: { sequence, Component } — receives { dashboard, reload }. */
export const receptionPanelRegistry = registry.category("careos.reception_dashboard_panels");

const REFRESH_MS = 30000;

export class ReceptionDashboard extends Component {
    static template = "careos_appointments.ReceptionDashboard";
    static components = { AppointmentActions, Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({ dashboard: null, error: "" });
        onWillStart(() => this.load());
        // Keep the counts current while the front desk leaves this open.
        const interval = setInterval(() => this.load(), REFRESH_MS);
        onWillUnmount(() => clearInterval(interval));
    }

    async load() {
        try {
            this.state.dashboard = await this.orm.call("careos.appointment", "careos_reception_dashboard", []);
            this.state.error = "";
        } catch (error) {
            this.state.error = error.data?.message || "The dashboard could not be loaded.";
        }
    }

    get d() {
        return this.state.dashboard;
    }

    get subtitle() {
        return `${DateTime.fromISO(this.d.date).toFormat("cccc, LLLL d")} · ${this.d.branch.name}`;
    }

    get panels() {
        return receptionPanelRegistry
            .getEntries()
            .map(([id, panel]) => ({ id, ...panel }))
            .sort((a, b) => (a.sequence ?? 10) - (b.sequence ?? 10));
    }

    tone(appointment) {
        return APPOINTMENT_TONE[appointment.state];
    }

    time(appointment) {
        return formatTime(appointment.start);
    }

    open(appointment) {
        this.env.careos.navigate("appointment", { resId: appointment.id });
    }

    registerPatient() {
        const session = this.env.careos.session;
        this.dialog.add(PatientFormDialog, {
            branches: session.branches,
            defaultBranchId: session.branch?.id || false,
            onSaved: (id) => this.env.careos.navigate("patient", { resId: id }),
            onOpenExisting: (id) => this.env.careos.navigate("patient", { resId: id }),
        });
    }

    book() {
        this.dialog.add(BookingDialog, { onSaved: () => this.load() });
    }
}

screenRegistry.add("dashboard", {
    label: "Dashboard",
    navGroup: "overview",
    sequence: 1,
    roles: ["reception", "nurse", "manager", "admin"],
    Component: ReceptionDashboard,
});
