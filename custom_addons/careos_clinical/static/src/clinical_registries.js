import { registry } from "@web/core/registry";

/**
 * Sections below the clinical notes on the encounter screen (prescription
 * lines, lab orders…). Entry: { sequence, Component } — receives
 * { encounter, reload }.
 */
export const encounterSectionRegistry = registry.category("careos.encounter_sections");

/**
 * Header buttons on the encounter screen ("+ Prescription", "+ Lab order").
 * Entry: { label, sequence, isVisible(encounter), run(encounter, env, reload) }
 */
export const encounterActionRegistry = registry.category("careos.encounter_actions");

/**
 * Right-column cards on the Doctor Workspace ("Pending lab results").
 * Entry: { sequence, Component } — receives { dashboard, reload }.
 */
export const doctorPanelRegistry = registry.category("careos.doctor_dashboard_panels");

export const ENCOUNTER_TONE = { open: "active", done: "success" };
