import { Component, onWillStart, useState } from "@odoo/owl";
import { deserializeDateTime, serializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;

const NAV = [
    ["home", "Home"],
    ["appointments", "Appointments"],
    ["rx", "Prescriptions"],
    ["lab", "Lab Results"],
    ["billing", "Billing"],
    ["messages", "Messages"],
];
const APPT_TONE = { draft: "neutral", confirmed: "info", checked_in: "warning", in_progress: "active", done: "success", no_show: "neutral" };
const RX_TONE = { issued: "info", dispensed: "success" };

function fmt(value, pattern) {
    return value ? deserializeDateTime(value).toFormat(pattern) : "";
}

/**
 * The patient portal (prototype "Patient Portal"). `source` supplies data
 * and actions: the real portal calls the patient JSON routes; the staff
 * preview reads the same payload and disables every action.
 */
export class PortalApp extends Component {
    static template = "careos_portal.PortalApp";
    static props = {
        source: Object,
        onExit: { type: Function, optional: true }, // staff preview: back to CareOS
    };

    setup() {
        this.nav = NAV;
        this.state = useState({
            screen: "home", data: null, error: "", draft: "", busy: false, notice: "",
            booking: null, reschedule: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.data = await this.props.source.load();
        } catch (error) {
            this.state.error = error.data?.message || error.message || "Your record could not be loaded.";
        }
    }

    get d() {
        return this.state.data;
    }

    get readonly() {
        return this.d?.preview;
    }

    get initials() {
        return this.d.patient.name.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
    }

    get newLabCount() {
        return this.d.lab_results.filter((r) => r.is_new).length;
    }

    go(screen) {
        this.state.screen = screen;
        this.state.notice = "";
    }

    when(value) {
        return fmt(value, "LLL d, HH:mm");
    }

    day(value) {
        return fmt(value, "ccc, LLL d");
    }

    money(value) {
        return `${Number(value || 0).toLocaleString()} ${this.d.currency}`;
    }

    apptTone(a) {
        return APPT_TONE[a.state] || "neutral";
    }

    rxTone(line) {
        return RX_TONE[line.state] || "neutral";
    }

    async act(call, notice) {
        if (this.readonly || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            this.state.data = await call();
            this.state.notice = notice || "";
        } catch (error) {
            this.state.notice = error.data?.message || error.message || "Something went wrong.";
        } finally {
            this.state.busy = false;
        }
    }

    // Messages
    async send() {
        const text = this.state.draft.trim();
        if (text) {
            await this.act(() => this.props.source.message(text));
            this.state.draft = "";
        }
    }

    // Reschedule request
    startReschedule(appointment) {
        this.state.reschedule = { appointment, note: "" };
    }

    async sendReschedule() {
        const { appointment, note } = this.state.reschedule;
        await this.act(() => this.props.source.reschedule(appointment.id, note),
            "Request sent. The clinic will reply in Messages.");
        this.state.reschedule = null;
    }

    // Booking request
    async startBooking() {
        if (this.readonly) {
            return;
        }
        const options = await this.props.source.bookingOptions();
        this.state.booking = {
            options, providerId: String(options.providers[0]?.id || ""), typeId: String(options.types[0]?.id || ""),
            day: options.day, time: "", reason: "",
        };
    }

    onProviderChange(ev) {
        this.state.booking.providerId = ev.target.value;
        this.state.booking.time = "";
    }

    async changeBookingDay(ev) {
        const options = await this.props.source.bookingOptions(ev.target.value);
        Object.assign(this.state.booking, { options, day: options.day, time: "" });
    }

    get slots() {
        const b = this.state.booking;
        if (!b) {
            return [];
        }
        const type = b.options.types.find((t) => String(t.id) === b.typeId);
        const duration = type?.duration || 30;
        const busy = (b.options.busy[b.providerId] || []).map((i) => ({
            start: deserializeDateTime(i.start), stop: deserializeDateTime(i.stop),
        }));
        const slots = [];
        let slot = DateTime.fromISO(b.day).set({ hour: Math.floor(b.options.work_start), minute: (b.options.work_start % 1) * 60 });
        const end = DateTime.fromISO(b.day).set({ hour: Math.floor(b.options.work_end), minute: (b.options.work_end % 1) * 60 });
        while (slot.plus({ minutes: duration }) <= end) {
            const stop = slot.plus({ minutes: duration });
            if (slot > DateTime.now() && !busy.some((i) => slot < i.stop && stop > i.start)) {
                slots.push(slot.toFormat("HH:mm"));
            }
            slot = slot.plus({ minutes: 30 });
        }
        return slots;
    }

    async sendBooking() {
        const b = this.state.booking;
        if (!b.time) {
            this.state.notice = "Choose a time.";
            return;
        }
        const start = serializeDateTime(DateTime.fromISO(`${b.day}T${b.time}`));
        await this.act(() => this.props.source.book({
            provider_id: parseInt(b.providerId), type_id: parseInt(b.typeId), start, reason: b.reason,
        }), "Appointment requested. The clinic will confirm it shortly.");
        this.state.booking = null;
        this.state.screen = "appointments";
    }
}
