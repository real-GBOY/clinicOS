import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { PortalApp } from "../portal/portal_app";

/** Data source for the logged-in patient: the portal JSON routes. */
const patientSource = {
    load: () => rpc("/careos/portal/data"),
    message: (text) => rpc("/careos/portal/message", { text }),
    reschedule: (appointmentId, note) => rpc("/careos/portal/reschedule", { appointment_id: appointmentId, note }),
    bookingOptions: (day) => rpc("/careos/portal/booking_options", { day: day || null }),
    book: (vals) => rpc("/careos/portal/book", vals),
};

export class PortalPage extends Component {
    static template = xml`<PortalApp source="source"/>`;
    static components = { PortalApp };
    static props = ["*"];

    setup() {
        this.source = patientSource;
    }
}

registry.category("public_components").add("careos_portal.PortalPage", PortalPage);
