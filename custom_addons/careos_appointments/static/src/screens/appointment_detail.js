import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Avatar, Badge, EmptyState, LoadingState, Timeline } from "@careos_base/components/primitives";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { AppointmentActions } from "../components/appointment_actions";
import { APPOINTMENT_TONE, formatDay, formatTime, relativeDay } from "../appointment_utils";

export class AppointmentDetail extends Component {
    static template = "careos_appointments.AppointmentDetail";
    static components = { AppointmentActions, Avatar, Badge, EmptyState, LoadingState, Timeline };
    static props = { params: Object };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ appointment: null, error: "" });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            const appointment = await this.orm.call("careos.appointment", "careos_get_detail", [[this.props.params.resId]]);
            this.state.appointment = appointment;
            this.env.careos.setPageTitle(`${appointment.name} · ${appointment.patient.name}`);
        } catch (error) {
            this.state.error = error.data?.message || "This appointment could not be opened.";
        }
    }

    get a() {
        return this.state.appointment;
    }

    get tone() {
        return APPOINTMENT_TONE[this.a.state];
    }

    get when() {
        return `${relativeDay(this.a.start)} · ${formatTime(this.a.start)}–${formatTime(this.a.stop)}`;
    }

    get detailRows() {
        const a = this.a;
        return [
            ["Date", formatDay(a.start)],
            ["Time", `${formatTime(a.start)}–${formatTime(a.stop)} (${a.duration} min)`],
            ["Provider", a.provider.name],
            ["Visit type", a.type.name],
            ["Room", a.room ? a.room.name : "Not assigned"],
            ["Branch", a.branch.name],
            ["Reason", a.reason || "—"],
        ];
    }

    get historyEvents() {
        return [...this.a.history].reverse().map((e) => ({ ...e, date: `${formatDay(e.date)} ${formatTime(e.date)}` }));
    }

    openPatient() {
        this.env.careos.navigate("patient", { resId: this.a.patient.id });
    }

    back() {
        this.env.careos.navigate("appointments");
    }
}

screenRegistry.add("appointment", {
    label: "Appointment",
    parent: "appointments",
    roles: ["reception", "doctor", "nurse", "manager", "admin"],
    Component: AppointmentDetail,
});
