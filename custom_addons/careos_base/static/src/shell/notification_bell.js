import { Component, onWillStart, onWillUnmount, useExternalListener, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { topbarRegistry } from "./screen_registry";

const { DateTime } = luxon;
const REFRESH_MS = 60000;

const DOT_CLASS = {
    info: "co-notif__dot--info",
    success: "co-notif__dot--success",
    warning: "co-notif__dot--warning",
    danger: "co-notif__dot--danger",
    insight: "co-notif__dot--info",
};

/** Top-bar bell: the user's own notifications (prototype "Notifications"). */
export class NotificationBell extends Component {
    static template = "careos_base.NotificationBell";
    static props = { screen: { type: [String, { value: null }], optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ open: false, unread: 0, items: [] });
        onWillStart(() => this.load());
        const interval = setInterval(() => this.load(), REFRESH_MS);
        onWillUnmount(() => clearInterval(interval));
        useExternalListener(window, "click", () => (this.state.open = false));
    }

    async load() {
        try {
            Object.assign(this.state, await this.orm.silent.call("careos.notification", "careos_inbox", []));
        } catch {
            // The bell is non-essential; keep the last known state.
        }
    }

    toggle(ev) {
        ev.stopPropagation();
        this.state.open = !this.state.open;
        if (this.state.open) {
            this.load();
        }
    }

    dotClass(item) {
        return DOT_CLASS[item.kind] || DOT_CLASS.info;
    }

    when(item) {
        return DateTime.fromSQL(item.date, { zone: "utc" }).toRelative();
    }

    async open(item) {
        this.state.open = false;
        if (!item.is_read) {
            await this.orm.call("careos.notification", "careos_mark_read", [[item.id]]);
        }
        if (item.screen) {
            this.env.careos.navigate(item.screen, item.res_id ? { resId: item.res_id } : {});
        }
        this.load();
    }

    async markAllRead(ev) {
        ev.stopPropagation();
        await this.orm.call("careos.notification", "careos_mark_all_read", []);
        this.load();
    }
}

topbarRegistry.add("notifications", { sequence: 50, Component: NotificationBell });
