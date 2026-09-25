import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { dashboardRegistry, screenRegistry } from "@careos_base/shell/screen_registry";

/**
 * Single-series horizontal bars (one hue for magnitude). Values are direct
 * labels in text ink; each row has a hover tooltip. A row can be flagged
 * (status colour + a text label, never colour alone).
 */
export class BarList extends Component {
    static template = "careos_analytics.BarList";
    static props = { rows: Array, emptyText: { type: String, optional: true }, flagLabel: { type: String, optional: true } };

    tooltip(row) {
        return `${row.name}: ${row.label}${row.count ? ` (${row.count} visits)` : ""}`;
    }
}

/** Prototype "Manager Workspace". */
export class ManagerDashboard extends Component {
    static template = "careos_analytics.ManagerDashboard";
    static components = { BarList, EmptyState, LoadingState, PageHeader };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ d: null, error: "" });
        onWillStart(async () => {
            try {
                this.state.d = await this.orm.call("careos.analytics", "careos_manager_dashboard", []);
            } catch (error) {
                this.state.error = error.data?.message || "The workspace could not be loaded.";
            }
        });
    }

    open(kpi) {
        this.env.careos.navigate(kpi.screen, kpi.tab ? { tab: kpi.tab } : {});
    }

    investigate() {
        this.env.careos.navigate("analytics", { tab: "operations" });
    }
}

const TABS = [["operations", "Operations"], ["finance", "Finance"], ["patients", "Patients"]];

/** Prototype "Analytics" with Operations / Finance / Patients tabs. */
export class AnalyticsScreen extends Component {
    static template = "careos_analytics.AnalyticsScreen";
    static components = { BarList, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.tabs = TABS;
        this.state = useState({ tab: this.props.params?.tab || "operations", days: 30, data: null, error: "" });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = null;
        try {
            this.state.data = await this.orm.call("careos.analytics", "careos_analytics", [], {
                tab: this.state.tab,
                days: this.state.days,
            });
        } catch (error) {
            this.state.error = error.data?.message || "Analytics could not be loaded.";
        }
    }

    setTab(tab) {
        this.state.tab = tab;
        this.load();
    }

    setDays(ev) {
        this.state.days = parseInt(ev.target.value);
        this.load();
    }

    get subtitle() {
        return `${this.state.data?.branch || ""} · Last ${this.state.days} days`;
    }
}

dashboardRegistry.add("manager", {
    label: "Manager",
    sequence: 30,
    roles: ["manager", "admin"],
    defaultFor: ["manager"],
    Component: ManagerDashboard,
});
screenRegistry.add("analytics", {
    label: "Analytics",
    navGroup: "analytics",
    sequence: 10,
    roles: ["manager", "admin", "finance"],
    Component: AnalyticsScreen,
});
