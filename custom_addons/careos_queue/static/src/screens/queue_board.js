import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { formatTime, minutesSince } from "@careos_appointments/appointment_utils";

const REFRESH_MS = 15000;

export const TICKET_ACTIONS = {
    call: { label: "Call patient", style: "primary", method: "action_call" },
    start: { label: "Start consultation", style: "primary", method: "action_start" },
    complete: { label: "Complete visit", style: "success", method: "action_complete" },
    no_show: { label: "No-show", style: "ghost", method: "action_no_show" },
};

/** Live queue for today at the current branch (prototype "Live Queue"). */
export class QueueBoard extends Component {
    static template = "careos_queue.QueueBoard";
    static components = { Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ board: null, error: "", busy: false });
        onWillStart(() => this.load());
        const interval = setInterval(() => this.load(), REFRESH_MS);
        onWillUnmount(() => clearInterval(interval));
    }

    async load() {
        try {
            this.state.board = await this.orm.call("careos.queue.ticket", "careos_queue_board", []);
            this.state.error = "";
        } catch (error) {
            this.state.error = error.data?.message || "The queue could not be loaded.";
        }
    }

    get b() {
        return this.state.board;
    }

    get subtitle() {
        const parts = [this.b.branch.name];
        if (this.b.no_show_count) {
            parts.push(`${this.b.no_show_count} no-show${this.b.no_show_count > 1 ? "s" : ""}`);
        }
        return parts.join(" · ");
    }

    actionsFor(ticket) {
        return ticket.actions.map((key) => ({ key, ...TICKET_ACTIONS[key] }));
    }

    waited(ticket) {
        return minutesSince(ticket.checked_in_at);
    }

    time(value) {
        return formatTime(value);
    }

    async run(ticket, action) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("careos.queue.ticket", TICKET_ACTIONS[action].method, [[ticket.id]]);
            if (action === "call") {
                const room = ticket.appointment && ticket.room ? ` to ${ticket.room.name}` : "";
                this.notification.add(`${ticket.patient.name} called${room}.`, { type: "info" });
            }
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "The queue could not be updated.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openPatient(ticket) {
        this.env.careos.navigate("patient", { resId: ticket.patient.id });
    }

    openAppointment(ticket) {
        this.env.careos.navigate("appointment", { resId: ticket.appointment.id });
    }
}

screenRegistry.add("queue", {
    label: "Queue",
    navGroup: "operations",
    sequence: 20,
    roles: ["reception", "nurse", "doctor", "manager", "admin"],
    Component: QueueBoard,
});
