import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Avatar, Badge, EmptyState, LoadingState } from "@careos_base/components/primitives";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { PatientFormDialog } from "../dialogs/patient_form_dialog";

/**
 * Tabs of the Patient 360. Domain modules add their own section:
 *
 *   patientTabRegistry.add("billing", {
 *       label: "Billing", sequence: 50, Component: PatientBilling,
 *       isVisible: (profile) => ..., count: (profile) => ...,
 *   });
 *
 * Each tab component receives { profile, reload }.
 */
export const patientTabRegistry = registry.category("careos.patient_tabs");

export class Patient360 extends Component {
    static template = "careos_patients.Patient360";
    static components = { Avatar, Badge, EmptyState, LoadingState };
    static props = { params: Object };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({ profile: null, error: "", tab: this.props.params.tab || "overview" });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            const profile = await this.orm.call("careos.patient", "careos_get_profile", [[this.props.params.resId]]);
            this.state.profile = profile;
            this.state.error = "";
            this.env.careos.setPageTitle(profile.name);
        } catch (error) {
            this.state.error = error.data?.message || "This patient record could not be opened.";
        }
    }

    get tabs() {
        const profile = this.state.profile;
        return patientTabRegistry
            .getEntries()
            .map(([id, tab]) => ({ id, ...tab }))
            .filter((tab) => !tab.isVisible || tab.isVisible(profile))
            .sort((a, b) => (a.sequence ?? 10) - (b.sequence ?? 10))
            .map((tab) => ({ ...tab, countValue: tab.count ? tab.count(profile) : null }));
    }

    get activeTab() {
        const tabs = this.tabs;
        return tabs.find((t) => t.id === this.state.tab) || tabs[0];
    }

    get metaLine() {
        const p = this.state.profile;
        const parts = [];
        if (p.age !== null) {
            parts.push(`${p.age}y`);
        }
        if (p.sex_label) {
            parts.push(p.sex_label);
        }
        if (p.phone) {
            parts.push(p.phone);
        }
        parts.push(p.insurance_provider ? `Insurance: ${p.insurance_provider}` : "Self-pay");
        return parts.join(" · ");
    }

    get headerBadges() {
        const p = this.state.profile;
        const badges = p.allergies.map((a) => ({
            key: `a${a.id}`,
            label: `${a.allergen} allergy`,
            tone: a.severity === "mild" ? "warning" : "danger",
        }));
        for (const c of p.conditions || []) {
            if (c.status !== "resolved") {
                badges.push({ key: `c${c.id}`, label: c.name, tone: "warning" });
            }
        }
        return badges;
    }

    edit() {
        const session = this.env.careos.session;
        this.dialog.add(PatientFormDialog, {
            patient: this.state.profile,
            branches: session.branches,
            onSaved: () => this.load(),
        });
    }

    backToDirectory() {
        this.env.careos.navigate("patients");
    }
}

screenRegistry.add("patient", {
    label: "Patient",
    parent: "patients",
    Component: Patient360,
});
