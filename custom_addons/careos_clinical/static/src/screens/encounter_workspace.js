import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { formatTime } from "@careos_appointments/appointment_utils";
import { ENCOUNTER_TONE, encounterActionRegistry, encounterSectionRegistry } from "../clinical_registries";
import { VitalsDialog } from "../dialogs/vitals_dialog";

const TEXT_FIELDS = ["chief_complaint", "notes", "plan", "follow_up_reason", "follow_up_date"];

/**
 * The consultation screen (prototype "Consultation — Ahmed Hassan"): vitals,
 * chief complaint, diagnosis and notes on one page, with prescribing and lab
 * ordering contributed by their modules. Text is saved when a field loses
 * focus; the server enforces who may edit what.
 */
export class EncounterWorkspace extends Component {
    static template = "careos_clinical.EncounterWorkspace";
    static components = { Badge, EmptyState, LoadingState };
    static props = { params: Object };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            enc: null,
            error: "",
            draft: {},
            dx: { code: "", description: "", is_primary: false },
            saving: false,
            completing: false,
        });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            const enc = await this.orm.call("careos.encounter", "careos_get_workspace", [[this.props.params.resId]]);
            this.apply(enc);
        } catch (error) {
            this.state.error = error.data?.message || "This encounter could not be opened.";
        }
    }

    apply(enc) {
        this.state.enc = enc;
        this.state.draft = Object.fromEntries(TEXT_FIELDS.map((f) => [f, enc[f] || ""]));
        this.env.careos.setPageTitle(`Consultation · ${enc.patient.name}`);
    }

    get e() {
        return this.state.enc;
    }

    get subtitle() {
        const e = this.e;
        const ctx = e.patient_context;
        const parts = [];
        if (ctx.age !== null) {
            parts.push(`${ctx.age}y ${ctx.sex}`.trim());
        }
        parts.push(`Appointment ${formatTime(e.appointment.start)}`);
        parts.push(e.type + (e.appointment.reason ? `: ${e.appointment.reason}` : ""));
        return parts.join(" · ");
    }

    get tone() {
        return ENCOUNTER_TONE[this.e.state];
    }

    get headerActions() {
        return encounterActionRegistry
            .getEntries()
            .map(([id, action]) => ({ id, ...action }))
            .filter((action) => !action.isVisible || action.isVisible(this.e))
            .sort((a, b) => (a.sequence ?? 10) - (b.sequence ?? 10));
    }

    get sections() {
        return encounterSectionRegistry
            .getEntries()
            .map(([id, section]) => ({ id, ...section }))
            .sort((a, b) => (a.sequence ?? 10) - (b.sequence ?? 10));
    }

    formatDate(value) {
        return formatDisplayDate(value);
    }

    // ------------------------------------------------------------------
    // Editing
    // ------------------------------------------------------------------

    async saveField(field) {
        const value = this.state.draft[field];
        if ((this.e[field] || "") === value) {
            return;
        }
        this.state.saving = true;
        try {
            this.apply(await this.orm.call("careos.encounter", "careos_save", [[this.e.id], { [field]: value }]));
        } catch (error) {
            this.notification.add(error.data?.message || "Could not save.", { type: "danger" });
            this.state.draft[field] = this.e[field] || "";
        } finally {
            this.state.saving = false;
        }
    }

    recordVitals() {
        this.dialog.add(VitalsDialog, {
            encounterId: this.e.id,
            patientName: this.e.patient.name,
            onSaved: () => this.load(),
        });
    }

    async addDiagnosis() {
        const dx = this.state.dx;
        if (!dx.description.trim()) {
            this.notification.add("Enter a diagnosis description.", { type: "warning" });
            return;
        }
        try {
            await this.orm.create("careos.diagnosis", [{
                encounter_id: this.e.id,
                code: dx.code,
                description: dx.description,
                is_primary: dx.is_primary || !this.e.diagnoses.length,
            }]);
            this.state.dx = { code: "", description: "", is_primary: false };
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "Could not add the diagnosis.", { type: "danger" });
        }
    }

    async removeDiagnosis(dx) {
        try {
            await this.orm.unlink("careos.diagnosis", [dx.id]);
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "Could not remove the diagnosis.", { type: "danger" });
        }
    }

    async complete() {
        this.state.completing = true;
        try {
            await this.orm.call("careos.encounter", "action_complete", [[this.e.id]]);
            this.notification.add(`Encounter for ${this.e.patient.name} completed.`, { type: "success" });
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "The encounter could not be completed.", { type: "danger" });
        } finally {
            this.state.completing = false;
        }
    }

    runAction(action) {
        action.run(this.e, this.env, () => this.load());
    }

    openPatient() {
        this.env.careos.navigate("patient", { resId: this.e.patient.id });
    }

    openEncounter(encounter) {
        this.env.careos.navigate("encounter", { resId: encounter.id });
    }
}

screenRegistry.add("encounter", {
    label: "Encounter",
    parent: "encounters",
    roles: ["doctor", "nurse"],
    Component: EncounterWorkspace,
});
