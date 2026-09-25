import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { EmptyState, LoadingState } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { patientTabRegistry } from "../screens/patient_360";

/**
 * Internal notes on the patient record. Patient-facing messaging (SMS,
 * WhatsApp, portal) arrives with the communications module and will render
 * in this same thread.
 */
export class PatientCommunication extends Component {
    static template = "careos_patients.PatientCommunication";
    static components = { EmptyState, LoadingState };
    static props = { profile: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ messages: null, error: "", draft: "", posting: false, postError: "" });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            const messages = await this.orm.call("careos.patient", "careos_get_messages", [[this.props.profile.id]]);
            // Bodies are sanitized HTML produced by the mail module.
            this.state.messages = messages.map((m) => ({ ...m, body: markup(m.body) }));
        } catch (error) {
            this.state.error = error.data?.message || "Notes could not be loaded.";
        }
    }

    async post() {
        const text = this.state.draft.trim();
        if (!text || this.state.posting) {
            return;
        }
        this.state.posting = true;
        this.state.postError = "";
        try {
            await this.orm.call("careos.patient", "careos_post_note", [[this.props.profile.id], text]);
            this.state.draft = "";
            await Promise.all([this.load(), this.props.reload()]);
        } catch (error) {
            this.state.postError = error.data?.message || "The note could not be saved.";
        } finally {
            this.state.posting = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            this.post();
        }
    }

    when(message) {
        const dt = deserializeDateTime(message.date);
        return `${formatDisplayDate(message.date)} · ${dt.toFormat("HH:mm")}`;
    }
}

patientTabRegistry.add("communication", {
    label: "Notes",
    sequence: 30,
    Component: PatientCommunication,
});
