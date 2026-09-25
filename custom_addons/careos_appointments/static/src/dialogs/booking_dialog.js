import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CareModal } from "@careos_base/components/modal";
import { RecordPicker } from "@careos_base/components/record_picker";
import { toLocal, toServerDateTime } from "../appointment_utils";

const { DateTime } = luxon;

const SLOT_MINUTES = 15;
const DAY_START_HOUR = 7;
const DAY_END_HOUR = 21;

/**
 * Book a new appointment or reschedule an existing one. Slots that overlap
 * the provider's existing bookings are shown as unavailable; the server is
 * the authority on conflicts (provider, room and patient).
 */
export class BookingDialog extends Component {
    static template = "careos_appointments.BookingDialog";
    static components = { CareModal, RecordPicker };
    static props = {
        close: Function,
        onSaved: Function,
        appointment: { type: Object, optional: true }, // reschedule mode
        patient: { type: Object, optional: true }, // { id, display_name } prefill
    };

    setup() {
        this.orm = useService("orm");
        const a = this.props.appointment;
        const start = a ? toLocal(a.start) : null;
        this.state = useState({
            options: null,
            patient: a ? { id: a.patient.id, display_name: a.patient.name } : this.props.patient || null,
            providerId: a ? String(a.provider.id) : "",
            typeId: a ? String(a.type.id) : "",
            roomId: a?.room ? String(a.room.id) : "",
            day: start ? start.toISODate() : DateTime.now().toISODate(),
            time: start ? start.toFormat("HH:mm") : "",
            duration: a ? a.duration : 0,
            reason: a?.reason || "",
            notes: a?.notes || "",
            confirm: true,
            busy: [],
            errors: {},
            serverError: "",
            saving: false,
        });
        this.today = DateTime.now().toISODate();
        onWillStart(async () => {
            this.state.options = await this.orm.call("careos.appointment", "careos_booking_options", [], {
                branch_id: a?.branch.id || false,
            });
            if (!this.state.typeId && this.state.options.types.length) {
                this.onTypeChange(String(this.state.options.types[0].id));
            }
            await this.loadBusy();
        });
    }

    get isReschedule() {
        return Boolean(this.props.appointment);
    }

    get title() {
        return this.isReschedule ? `Reschedule ${this.props.appointment.name}` : "Book appointment";
    }

    onTypeChange(typeId) {
        this.state.typeId = typeId;
        const type = this.state.options.types.find((t) => String(t.id) === typeId);
        if (type) {
            this.state.duration = type.duration;
        }
    }

    async onProviderChange(providerId) {
        this.state.providerId = providerId;
        const provider = this.state.options.providers.find((p) => String(p.id) === providerId);
        if (provider?.default_room_id) {
            this.state.roomId = String(provider.default_room_id);
        }
        await this.loadBusy();
    }

    async onDayChange(ev) {
        this.state.day = ev.target.value;
        await this.loadBusy();
    }

    async loadBusy() {
        const { providerId, day } = this.state;
        if (!providerId || !day) {
            this.state.busy = [];
            return;
        }
        const busy = await this.orm.call("careos.appointment", "careos_provider_day", [parseInt(providerId), day], {
            exclude_id: this.props.appointment?.id || false,
        });
        this.state.busy = busy.map((b) => ({ start: toLocal(b.start), stop: toLocal(b.stop) }));
    }

    get slots() {
        const { day, duration, busy } = this.state;
        if (!day) {
            return [];
        }
        const now = DateTime.now();
        const slots = [];
        let slot = DateTime.fromISO(`${day}T00:00`).set({ hour: DAY_START_HOUR });
        const end = slot.set({ hour: DAY_END_HOUR });
        while (slot < end) {
            const stop = slot.plus({ minutes: duration || SLOT_MINUTES });
            const taken = busy.some((b) => slot < b.stop && stop > b.start);
            const past = slot < now.minus({ minutes: SLOT_MINUTES });
            const value = slot.toFormat("HH:mm");
            slots.push({ value, label: taken ? `${value} — booked` : value, disabled: taken || past });
            slot = slot.plus({ minutes: SLOT_MINUTES });
        }
        return slots;
    }

    validate() {
        const s = this.state;
        const errors = {};
        if (!s.patient) {
            errors.patient = "Choose a patient";
        }
        if (!s.providerId) {
            errors.provider = "Choose a provider";
        }
        if (!s.typeId) {
            errors.type = "Choose a visit type";
        }
        if (!s.day) {
            errors.day = "Choose a date";
        }
        if (!s.time) {
            errors.time = "Choose a time";
        }
        this.state.errors = errors;
        return !Object.keys(errors).length;
    }

    async save() {
        if (this.state.saving || !this.validate()) {
            return;
        }
        const s = this.state;
        const vals = {
            provider_id: parseInt(s.providerId),
            type_id: parseInt(s.typeId),
            room_id: s.roomId ? parseInt(s.roomId) : false,
            start: toServerDateTime(s.day, s.time),
            duration: parseInt(s.duration),
            reason: s.reason,
            notes: s.notes,
        };
        this.state.saving = true;
        this.state.serverError = "";
        try {
            let payload;
            if (this.isReschedule) {
                payload = await this.orm.call("careos.appointment", "careos_reschedule", [[this.props.appointment.id], vals]);
            } else {
                vals.patient_id = s.patient.id;
                vals.branch_id = s.options.branch.id;
                payload = await this.orm.call("careos.appointment", "careos_book", [vals], { confirm: s.confirm });
            }
            await this.props.onSaved(payload);
            this.props.close();
        } catch (error) {
            this.state.serverError = error.data?.message || "The appointment could not be saved.";
        } finally {
            this.state.saving = false;
        }
    }
}
