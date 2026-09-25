import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState } from "@careos_base/components/primitives";
import { patientTabRegistry } from "@careos_patients/screens/patient_360";
import { patientOverviewCardRegistry } from "@careos_patients/tabs/patient_overview";
import { AppointmentActions } from "../components/appointment_actions";
import { BookingDialog } from "../dialogs/booking_dialog";
import { APPOINTMENT_TONE, formatDay, formatTime, relativeDay } from "../appointment_utils";

function bookFor(component, profile, reload) {
    component.dialog.add(BookingDialog, {
        patient: { id: profile.id, display_name: `${profile.name} (${profile.ref})` },
        onSaved: () => reload(),
    });
}

/** Patient 360 → Appointments: upcoming and past visits. */
export class PatientAppointments extends Component {
    static template = "careos_appointments.PatientAppointments";
    static components = { AppointmentActions, Badge, EmptyState, LoadingState };
    static props = { profile: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({ data: null, error: "" });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.data = await this.orm.call("careos.patient", "careos_get_appointments", [[this.props.profile.id]]);
        } catch (error) {
            this.state.error = error.data?.message || "Appointments could not be loaded.";
        }
    }

    async refresh() {
        await Promise.all([this.load(), this.props.reload()]);
    }

    tone(appointment) {
        return APPOINTMENT_TONE[appointment.state];
    }

    when(appointment) {
        return `${formatDay(appointment.start)} · ${formatTime(appointment.start)}`;
    }

    open(appointment) {
        this.env.careos.navigate("appointment", { resId: appointment.id });
    }

    book() {
        bookFor(this, this.props.profile, () => this.refresh());
    }
}

/** Overview card: the patient's next (or current) visit, with check-in. */
export class NextAppointmentCard extends Component {
    static template = "careos_appointments.NextAppointmentCard";
    static components = { AppointmentActions, Badge };
    static props = { profile: Object, reload: Function };

    setup() {
        this.dialog = useService("dialog");
    }

    get appt() {
        return this.props.profile.next_appointment;
    }

    get tone() {
        return APPOINTMENT_TONE[this.appt.state];
    }

    get when() {
        return `${relativeDay(this.appt.start)} · ${formatTime(this.appt.start)}`;
    }

    open() {
        this.env.careos.navigate("appointment", { resId: this.appt.id });
    }

    book() {
        bookFor(this, this.props.profile, this.props.reload);
    }
}

patientTabRegistry.add("appointments", {
    label: "Appointments",
    sequence: 10,
    Component: PatientAppointments,
    isVisible: (profile) => profile.appointments_access,
    count: (profile) => profile.appointment_count,
});

patientOverviewCardRegistry.add("next_appointment", {
    sequence: 1,
    Component: NextAppointmentCard,
    isVisible: (profile) => profile.appointments_access && (profile.next_appointment || profile.can_book),
});
