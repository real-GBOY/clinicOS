import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { BookingDialog } from "@careos_appointments/dialogs/booking_dialog";

/** Patients.Follow-ups (spec IA): reviews due within a week or overdue, not yet booked. */
export class FollowUps extends Component {
    static template = "careos_clinical.FollowUps";
    static components = { Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({ rows: null, error: "" });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.rows = await this.orm.call("careos.encounter", "careos_follow_ups", [], { days: 7 });
        } catch (error) {
            this.state.error = error.data?.message || "Follow-ups could not be loaded.";
        }
    }

    get canBook() {
        return this.env.careos.session.roles.some((r) => ["reception", "admin"].includes(r));
    }

    due(row) {
        return formatDisplayDate(row.due);
    }

    book(row) {
        this.dialog.add(BookingDialog, {
            patient: { id: row.patient.id, display_name: row.patient.name },
            onSaved: () => this.load(),
        });
    }

    openPatient(row) {
        this.env.careos.navigate("patient", { resId: row.patient.id });
    }
}

screenRegistry.add("follow_ups", {
    label: "Follow-ups",
    navGroup: "clinical",
    sequence: 15,
    roles: ["reception", "doctor", "nurse", "manager"],
    Component: FollowUps,
});
