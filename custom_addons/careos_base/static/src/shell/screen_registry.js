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
 *       parent: "patients",         // (detail screens) breadcrumb parent
 *       Component: PatientDirectory,
 *   });
 *
 * `roles` only shapes navigation. Access is enforced server-side by groups,
 * ACLs and record rules; a screen must cope with AccessError like any client.
 */
export const screenRegistry = registry.category("careos.screens");

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

export function isScreenAllowed(screen, roles) {
    return !screen.roles || screen.roles.some((role) => roles.includes(role));
}
