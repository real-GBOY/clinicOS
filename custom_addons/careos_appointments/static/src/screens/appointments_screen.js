import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { AppointmentActions } from "../components/appointment_actions";
import { BookingDialog } from "../dialogs/booking_dialog";
import { APPOINTMENT_STATES, APPOINTMENT_TONE, formatTime, toLocal } from "../appointment_utils";

const { DateTime } = luxon;

const SLOT_MINUTES = 30;
const DEFAULT_FIRST_HOUR = 8;
const DEFAULT_LAST_HOUR = 17;

export class AppointmentsScreen extends Component {
    static template = "careos_appointments.AppointmentsScreen";
    static components = { AppointmentActions, Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.states = APPOINTMENT_STATES;
        this.state = useState({
            day: this.props.params?.day || DateTime.now().toISODate(),
            view: "schedule",
            stateFilter: "",
            providerId: "",
            query: "",
            records: null,
            total: 0,
            providers: [],
            canBook: false,
            error: "",
        });
        this.debouncedLoad = useDebounced(() => this.load(), 250);
        onWillStart(async () => {
            const [options, canBook] = await Promise.all([
                this.orm.call("careos.appointment", "careos_booking_options", []),
                this.orm.call("careos.appointment", "has_access", [[], "create"]),
                this.load(),
            ]);
            this.state.providers = options.providers;
            this.state.canBook = canBook;
        });
    }

    async load() {
        this.state.error = "";
        try {
            const result = await this.orm.call("careos.appointment", "careos_list", [], {
                filters: {
                    day: this.state.day,
                    state: this.state.stateFilter || false,
                    provider_id: this.state.providerId ? parseInt(this.state.providerId) : false,
                    query: this.state.query,
                },
                limit: 500,
            });
            this.state.records = result.records;
            this.state.total = result.total;
        } catch (error) {
            this.state.error = error.data?.message || "Appointments could not be loaded.";
        }
    }

    // ------------------------------------------------------------------
    // Filters and navigation
    // ------------------------------------------------------------------

    get dayLabel() {
        const day = DateTime.fromISO(this.state.day);
        const today = DateTime.now().startOf("day");
        const prefix = day.hasSame(today, "day") ? "Today · " : "";
        return prefix + day.toFormat("cccc, LLLL d");
    }

    shiftDay(days) {
        this.state.day = DateTime.fromISO(this.state.day).plus({ days }).toISODate();
        this.load();
    }

    goToday() {
        this.state.day = DateTime.now().toISODate();
        this.load();
    }

    onDayInput(ev) {
        if (ev.target.value) {
            this.state.day = ev.target.value;
            this.load();
        }
    }

    setFilter(key, value) {
        this.state[key] = value;
        this.load();
    }

    onQueryInput(ev) {
        this.state.query = ev.target.value;
        this.debouncedLoad();
    }

    // ------------------------------------------------------------------
    // Schedule grid (one column per provider, 30-minute rows)
    // ------------------------------------------------------------------

    get scheduleProviders() {
        const withBookings = new Set(this.state.records.map((a) => a.provider.id));
        return this.state.providers.filter(
            (p) => withBookings.has(p.id) || (!this.state.providerId && !this.state.stateFilter && !this.state.query)
        );
    }

    get scheduleRows() {
        const records = this.state.records;
        const starts = records.map((a) => toLocal(a.start));
        const first = Math.min(DEFAULT_FIRST_HOUR, ...starts.map((s) => s.hour));
        const last = Math.max(DEFAULT_LAST_HOUR, ...starts.map((s) => s.hour));
        const providers = this.scheduleProviders;
        const rows = [];
        for (let minutes = first * 60; minutes <= last * 60 + SLOT_MINUTES; minutes += SLOT_MINUTES) {
            const cells = providers.map((provider) => ({
                key: provider.id,
                appointments: records.filter((a, i) => {
                    const s = starts[i];
                    const m = s.hour * 60 + s.minute;
                    return a.provider.id === provider.id && m >= minutes && m < minutes + SLOT_MINUTES;
                }),
            }));
            const hh = String(Math.floor(minutes / 60)).padStart(2, "0");
            const mm = String(minutes % 60).padStart(2, "0");
            rows.push({ key: minutes, time: `${hh}:${mm}`, cells });
        }
        return rows;
    }

    tone(appointment) {
        return APPOINTMENT_TONE[appointment.state];
    }

    time(appointment) {
        return formatTime(appointment.start);
    }

    get isFiltered() {
        return Boolean(this.state.stateFilter || this.state.providerId || this.state.query.trim());
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------

    open(appointment) {
        this.env.careos.navigate("appointment", { resId: appointment.id });
    }

    book() {
        this.dialog.add(BookingDialog, {
            onSaved: (payload) => this.env.careos.navigate("appointment", { resId: payload.id }),
        });
    }
}

screenRegistry.add("appointments", {
    label: "Appointments",
    navGroup: "operations",
    sequence: 10,
    roles: ["reception", "doctor", "nurse", "manager", "admin"],
    Component: AppointmentsScreen,
});
