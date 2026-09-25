import { deserializeDateTime, serializeDateTime } from "@web/core/l10n/dates";

const { DateTime } = luxon;

/** Badge tone per appointment state (brand system "Appointment" badges). */
export const APPOINTMENT_TONE = {
    draft: "neutral",
    confirmed: "info",
    checked_in: "warning",
    in_progress: "active",
    done: "success",
    cancelled: "danger",
    no_show: "neutral",
};

export const APPOINTMENT_STATES = [
    ["draft", "Draft"],
    ["confirmed", "Confirmed"],
    ["checked_in", "Checked-in"],
    ["in_progress", "In Progress"],
    ["done", "Completed"],
    ["cancelled", "Cancelled"],
    ["no_show", "No-show"],
];

/** Button label and style per server action key. */
export const ACTION_META = {
    confirm: { label: "Confirm", style: "primary" },
    check_in: { label: "Check in", style: "primary" },
    start: { label: "Start consultation", style: "primary" },
    complete: { label: "Complete visit", style: "success" },
    reschedule: { label: "Reschedule", style: "secondary" },
    cancel: { label: "Cancel", style: "ghost" },
    no_show: { label: "No-show", style: "ghost" },
};

export function toLocal(value) {
    return value ? deserializeDateTime(value) : null;
}

export function formatTime(value) {
    const dt = toLocal(value);
    return dt ? dt.toFormat("HH:mm") : "";
}

export function formatDay(value) {
    const dt = toLocal(value);
    return dt ? dt.toFormat("ccc, LLL d") : "";
}

/** "Today", "Tomorrow" or "Tue, Sep 30". */
export function relativeDay(value) {
    const dt = toLocal(value);
    if (!dt) {
        return "";
    }
    const days = Math.round(dt.startOf("day").diff(DateTime.now().startOf("day"), "days").days);
    if (days === 0) {
        return "Today";
    }
    if (days === 1) {
        return "Tomorrow";
    }
    return dt.toFormat("ccc, LLL d");
}

/** Local date + "HH:mm" → server datetime string. */
export function toServerDateTime(isoDate, time) {
    return serializeDateTime(DateTime.fromISO(`${isoDate}T${time}`));
}

/** Whole minutes elapsed since a server datetime. */
export function minutesSince(value, now = DateTime.now()) {
    const dt = toLocal(value);
    return dt ? Math.max(0, Math.floor(now.diff(dt, "minutes").minutes)) : 0;
}
