import { registry } from "@web/core/registry";

/**
 * Screens rendered inside the CareOS shell. Domain modules register one entry
 * per workspace:
 *
 *   screenRegistry.add("patients", {
 *       label: "Patients",          // sidebar + breadcrumb label
 *       navGroup: "clinical",       // key in NAV_GROUPS; omit to hide from nav
 *       sequence: 10,               // order inside the group
 *       roles: ["reception", ...],  // CareOS role keys; omit = every role
 *       isAvailable: (session) => …, // optional extra condition
 *       parent: "patients",         // (detail screens) breadcrumb parent
 *       Component: PatientDirectory,
 *   });
 *
 * `roles` only shapes navigation. Access is enforced server-side by groups,
 * ACLs and record rules; a screen must cope with AccessError like any client.
 */
export const screenRegistry = registry.category("careos.screens");

/**
 * Role dashboards shown by the "Dashboard" screen (prototype role tabs):
 *   dashboardRegistry.add("reception", { label, roles, sequence, Component })
 */
export const dashboardRegistry = registry.category("careos.dashboards");

/**
 * Items in the top bar right side (notifications, AI assistant…):
 *   topbarRegistry.add("notifications", { sequence, Component })
 * Components receive { screen } (the current screen id).
 */
export const topbarRegistry = registry.category("careos.topbar_items");

/**
 * Buttons at the bottom of the sidebar ("Setup guide", "View as patient"):
 *   sidebarActionRegistry.add("setup", { label, sequence, roles, style, run(env) })
 */
export const sidebarActionRegistry = registry.category("careos.sidebar_actions");

export const NAV_GROUPS = [
    { key: "overview", label: "Overview" },
    { key: "clinical", label: "Clinical" },
    { key: "operations", label: "Operations" },
    { key: "finance", label: "Finance" },
    { key: "inventory", label: "Inventory" },
    { key: "communication", label: "Communication" },
    { key: "analytics", label: "Analytics" },
    { key: "settings", label: "Settings" },
];

export const ROLE_LABELS = {
    reception: "Reception",
    doctor: "Doctor",
    nurse: "Nurse",
    lab: "Laboratory",
    pharmacy: "Pharmacy",
    finance: "Finance",
    manager: "Manager",
    admin: "Administrator",
};

export function hasRole(roles, allowed) {
    return !allowed || allowed.some((role) => roles.includes(role));
}

export function isScreenAllowed(screen, roles, session) {
    return hasRole(roles, screen.roles) && (!screen.isAvailable || screen.isAvailable(session));
}

/** Dashboards available to a user, ordered. */
export function availableDashboards(roles) {
    return dashboardRegistry
        .getEntries()
        .map(([id, dashboard]) => ({ id, ...dashboard }))
        .filter((dashboard) => hasRole(roles, dashboard.roles))
        .sort((a, b) => (a.sequence ?? 10) - (b.sequence ?? 10));
}

/** The dashboard a user sees first: the first whose `defaultFor` roles match. */
export function defaultDashboard(roles) {
    const dashboards = availableDashboards(roles);
    return dashboards.find((d) => d.defaultFor && hasRole(roles, d.defaultFor)) || dashboards[0];
}
