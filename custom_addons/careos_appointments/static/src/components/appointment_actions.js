import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ACTION_META } from "../appointment_utils";
import { BookingDialog } from "../dialogs/booking_dialog";
import { CancelDialog } from "../dialogs/cancel_dialog";

const SERVER_METHOD = {
    confirm: "action_confirm",
    check_in: "action_check_in",
    start: "action_start",
    complete: "action_complete",
    no_show: "action_no_show",
};

/**
 * Workflow buttons for one appointment. The server decides which actions
 * are available (`appointment.actions`) and re-validates every call.
 */
export class AppointmentActions extends Component {
    static template = "careos_appointments.AppointmentActions";
    static props = {
        appointment: Object,
        onChanged: Function,
        only: { type: Array, optional: true }, // subset of actions to show
        small: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ busy: false });
    }

    get actions() {
        const only = this.props.only;
        return this.props.appointment.actions
            .filter((action) => !only || only.includes(action))
            .map((action) => ({ key: action, ...ACTION_META[action] }));
    }

    async run(action, ev) {
        ev?.stopPropagation();
        const appointment = this.props.appointment;
        if (action === "cancel") {
            this.dialog.add(CancelDialog, { appointment, onDone: () => this.props.onChanged() });
            return;
        }
        if (action === "reschedule") {
            this.dialog.add(BookingDialog, { appointment, onSaved: () => this.props.onChanged() });
            return;
        }
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("careos.appointment", SERVER_METHOD[action], [[appointment.id]]);
            if (action === "check_in") {
                this.notification.add(`${appointment.patient.name} is checked in and waiting.`, { type: "success" });
            }
            await this.props.onChanged();
        } catch (error) {
            this.notification.add(error.data?.message || "The action could not be completed.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}
