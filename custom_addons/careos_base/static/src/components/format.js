import { deserializeDate, deserializeDateTime, formatDate } from "@web/core/l10n/dates";

const { DateTime } = luxon;

/** "Sep 23, 2026" — CareOS date display used across screens. */
export function formatDisplayDate(value) {
    if (!value) {
        return "";
    }
    const dt = value.length > 10 ? deserializeDateTime(value) : deserializeDate(value);
    return dt.toLocaleString(DateTime.DATE_MED);
}

/** "Sep 23" for dates in the current year, otherwise the full date. */
export function formatShortDate(value) {
    if (!value) {
        return "";
    }
    const dt = value.length > 10 ? deserializeDateTime(value) : deserializeDate(value);
    return dt.year === DateTime.now().year ? dt.toFormat("LLL d") : formatDate(dt);
}
