import { Component } from "@odoo/owl";
import { Badge } from "@careos_base/components/primitives";
import { receptionPanelRegistry } from "@careos_appointments/screens/reception_dashboard";
import { minutesSince } from "@careos_appointments/appointment_utils";

/** Reception dashboard panel: who is waiting and who is being seen. */
export class QueuePanel extends Component {
    static template = "careos_queue.QueuePanel";
    static components = { Badge };
    static props = { dashboard: Object, reload: Function };

    get queue() {
        return this.props.dashboard.queue;
    }

    waited(ticket) {
        return minutesSince(ticket.checked_in_at);
    }

    openQueue() {
        this.env.careos.navigate("queue");
    }
}

receptionPanelRegistry.add("queue", { sequence: 10, Component: QueuePanel });
