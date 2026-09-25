import { Component } from "@odoo/owl";
import { EmptyState } from "../components/primitives";
import { availableDashboards, defaultDashboard, screenRegistry, topbarRegistry } from "./screen_registry";

/**
 * The "Dashboard" screen: shows the role dashboard for the current user.
 * Users with several roles switch between them with the tabs in the top bar
 * (prototype: Reception / Doctor / Manager).
 */
export class DashboardHost extends Component {
    static template = "careos_base.DashboardHost";
    static components = { EmptyState };
    static props = { params: { type: Object, optional: true } };

    get dashboards() {
        return availableDashboards(this.env.careos.session.roles);
    }

    get current() {
        const roles = this.env.careos.session.roles;
        return this.dashboards.find((d) => d.id === this.env.careos.ui.dashboard) || defaultDashboard(roles);
    }
}

export class DashboardTabs extends Component {
    static template = "careos_base.DashboardTabs";
    static props = { screen: { type: [String, { value: null }], optional: true } };

    get dashboards() {
        return availableDashboards(this.env.careos.session.roles);
    }

    get currentId() {
        const roles = this.env.careos.session.roles;
        return (this.dashboards.find((d) => d.id === this.env.careos.ui.dashboard) || defaultDashboard(roles))?.id;
    }

    select(id) {
        this.env.careos.ui.dashboard = id;
    }
}

screenRegistry.add("dashboard", {
    label: "Dashboard",
    navGroup: "overview",
    sequence: 1,
    isAvailable: (session) => availableDashboards(session.roles).length > 0,
    Component: DashboardHost,
});

topbarRegistry.add("dashboard_tabs", { sequence: 1, Component: DashboardTabs });
