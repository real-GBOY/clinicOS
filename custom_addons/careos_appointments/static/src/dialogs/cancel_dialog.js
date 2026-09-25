import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CareModal } from "@careos_base/components/modal";
import { formatDay, formatTime } from "../appointment_utils";

const COMMON_REASONS = ["Patient request", "Provider unavailable", "Rebooked at another time", "Duplicate booking"];

export class CancelDialog extends Component {
    static template = "careos_appointments.CancelDialog";
    static components = { CareModal };
    static props = { close: Function, appointment: Object, onDone: Function };

    setup() {
        this.orm = useService("orm");
        this.reasons = COMMON_REASONS;
        this.state = useState({ reason: "", error: "", saving: false });
    }

    get when() {
        const a = this.props.appointment;
        return `${formatDay(a.start)} at ${formatTime(a.start)} with ${a.provider.name}`;
    }

    async confirm() {
        if (!this.state.reason.trim()) {
            this.state.error = "Give a reason for the cancellation.";
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("careos.appointment", "action_cancel", [[this.props.appointment.id]], {
                reason: this.state.reason,
            });
            await this.props.onDone();
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || "The appointment could not be cancelled.";
        } finally {
            this.state.saving = false;
        }
    }
}
