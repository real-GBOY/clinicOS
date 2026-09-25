import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { formatShortDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { formatTime } from "@careos_appointments/appointment_utils";
import { patientTabRegistry } from "@careos_patients/screens/patient_360";

const REFRESH_MS = 30000;
const REMINDER_TONE = { scheduled: "info", sent: "success", failed: "danger", cancelled: "neutral" };

function when(value) {
    return `${formatShortDate(value)} · ${formatTime(value)}`;
}

/** A patient conversation with a reply box (shared by Inbox and Patient 360). */
export class ConversationThread extends Component {
    static template = "careos_communications.ConversationThread";
    static props = { patientId: Number, onSent: { type: Function, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ messages: null, draft: "", sending: false });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.messages = await this.orm.call("careos.patient", "careos_get_conversation", [[this.props.patientId]]);
    }

    when(message) {
        return when(message.date);
    }

    async send() {
        const text = this.state.draft.trim();
        if (!text || this.state.sending) {
            return;
        }
        this.state.sending = true;
        try {
            this.state.messages = await this.orm.call("careos.patient", "careos_send_message", [[this.props.patientId], text]);
            this.state.draft = "";
            this.props.onSent?.();
        } catch (error) {
            this.notification.add(error.data?.message || "The message could not be sent.", { type: "danger" });
        } finally {
            this.state.sending = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }
}

export class Inbox extends Component {
    static template = "careos_communications.Inbox";
    static components = { Badge, ConversationThread, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null, error: "", selected: this.props.params?.resId || null, threadKey: 0 });
        onWillStart(() => this.load());
        const interval = setInterval(() => this.load(), REFRESH_MS);
        onWillUnmount(() => clearInterval(interval));
    }

    async load() {
        try {
            this.state.data = await this.orm.call("careos.communications", "careos_inbox", []);
            if (!this.state.selected && this.state.data.conversations.length) {
                this.state.selected = this.state.data.conversations[0].patient.id;
            }
        } catch (error) {
            this.state.error = error.data?.message || "The inbox could not be loaded.";
        }
    }

    select(conversation) {
        this.state.selected = conversation.patient.id;
        this.state.threadKey++;
    }

    get selectedName() {
        return this.state.data.conversations.find((c) => c.patient.id === this.state.selected)?.patient.name || "";
    }

    when(value) {
        return when(value);
    }

    reminderTone(reminder) {
        return REMINDER_TONE[reminder.state];
    }

    async retry(reminder) {
        await this.orm.call("careos.communications", "careos_retry_reminder", [reminder.id]);
        await this.load();
    }

    openPatient() {
        this.env.careos.navigate("patient", { resId: this.state.selected });
    }
}

export class PatientConversation extends Component {
    static template = "careos_communications.PatientConversation";
    static components = { ConversationThread };
    static props = { profile: Object, reload: Function };
}

screenRegistry.add("inbox", {
    label: "Inbox",
    navGroup: "communication",
    sequence: 10,
    roles: ["reception", "doctor", "nurse", "manager", "admin"],
    Component: Inbox,
});
patientTabRegistry.add("messages", {
    label: "Communication",
    sequence: 30,
    Component: PatientConversation,
    isVisible: (profile) => profile.messages_access,
});
