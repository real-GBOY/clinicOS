import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { RecordPicker } from "@careos_base/components/record_picker";
import { PageHeader } from "@careos_base/components/primitives";
import { screenRegistry, sidebarActionRegistry } from "@careos_base/shell/screen_registry";
import { patientOverviewCardRegistry } from "@careos_patients/tabs/patient_overview";
import { PortalApp } from "../portal/portal_app";

/**
 * "View as patient" (prototype): staff see exactly what a patient sees in
 * the portal, read-only, for a patient they can access.
 */
export class PortalPreview extends Component {
    static template = "careos_portal.PortalPreview";
    static components = { PageHeader, PortalApp, RecordPicker };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ patient: null, key: 0 });
        if (this.props.params?.resId) {
            this.state.patient = { id: this.props.params.resId, display_name: "" };
        }
    }

    get source() {
        const orm = this.orm;
        const id = this.state.patient.id;
        const readonly = () => Promise.reject(new Error("Preview is read-only."));
        return {
            load: () => orm.call("careos.portal", "careos_preview", [id]),
            message: readonly,
            reschedule: readonly,
            bookingOptions: readonly,
            book: readonly,
        };
    }

    choose(record) {
        this.state.patient = record;
        this.state.key++;
    }

    exit() {
        this.env.careos.navigate("dashboard");
    }
}

/** Patient 360 overview: portal access status and invitation. */
export class PortalAccessCard extends Component {
    static template = "careos_portal.PortalAccessCard";
    static props = { profile: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async invite() {
        try {
            await this.orm.call("careos.patient", "careos_invite_portal", [[this.props.profile.id]]);
            this.notification.add("Portal invitation sent.", { type: "success" });
            await this.props.reload();
        } catch (error) {
            this.notification.add(error.data?.message || "The invitation could not be sent.", { type: "danger" });
        }
    }

    preview() {
        this.env.careos.navigate("portal_preview", { resId: this.props.profile.id });
    }
}

screenRegistry.add("portal_preview", {
    label: "Patient portal preview",
    roles: ["reception", "doctor", "nurse", "manager", "admin"],
    Component: PortalPreview,
});
sidebarActionRegistry.add("view_as_patient", {
    label: "View as patient →",
    sequence: 20,
    roles: ["reception", "doctor", "nurse", "manager", "admin"],
    run: (env) => env.careos.navigate("portal_preview"),
});
patientOverviewCardRegistry.add("portal_access", {
    sequence: 90,
    Component: PortalAccessCard,
    isVisible: (profile) => Boolean(profile.portal),
});
