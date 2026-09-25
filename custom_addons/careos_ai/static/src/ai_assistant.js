import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { availableDashboards, defaultDashboard, topbarRegistry } from "@careos_base/shell/screen_registry";

const APPLY_SECTIONS = [
    ["chief_complaint", "Chief complaint"],
    ["assessment", "Assessment (appended to notes)"],
    ["plan", "Plan"],
];

/** What the assistant can do on each screen. */
function contextFor(env) {
    const screen = env.careos.screen;
    const params = env.careos.params || {};
    if (screen === "patient" && params.resId) {
        return { kind: "patient", resId: params.resId };
    }
    if (screen === "encounter" && params.resId) {
        return { kind: "encounter", resId: params.resId };
    }
    if (screen === "invoice" && params.resId) {
        return { kind: "invoice", resId: params.resId };
    }
    if (screen === "dashboard") {
        const dashboards = availableDashboards(env.careos.session.roles);
        const current = dashboards.find((d) => d.id === env.careos.ui.dashboard) || defaultDashboard(env.careos.session.roles);
        if (current?.id === "manager") {
            return { kind: "manager", resId: 0 };
        }
        if (current?.id === "reception") {
            return { kind: "reception", resId: 0 };
        }
    }
    return null;
}

/**
 * Prototype "AI Assistant": contextual, clearly labelled, never a floating
 * chatbot. Output is AI-generated and requires review; the only write path
 * is the doctor applying reviewed sections of a structured note.
 */
export class AiAssistant extends Component {
    static template = "careos_ai.AiAssistant";
    static props = { screen: { type: [String, { value: null }], optional: true } };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.sections = APPLY_SECTIONS;
        this.state = useState({
            open: false, status: null, loading: false, error: "", result: null, context: null,
            apply: new Set(["chief_complaint", "plan"]), apiKey: "",
        });
        onWillStart(async () => {
            this.state.status = await this.orm.call("careos.ai", "careos_status", []);
        });
    }

    get visible() {
        return this.state.status?.can_use || this.state.status?.is_admin;
    }

    async toggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            this.state.context = contextFor(this.env);
            this.state.result = null;
            this.state.error = "";
            if (this.state.context && this.state.status.enabled) {
                await this.run();
            }
        }
    }

    close() {
        this.state.open = false;
    }

    async run() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.result = await this.orm.call("careos.ai", "careos_assist", [this.state.context.kind, this.state.context.resId]);
        } catch (error) {
            this.state.error = error.data?.message || "CareOS Intelligence is unavailable.";
        } finally {
            this.state.loading = false;
        }
    }

    toggleSection(key) {
        const apply = this.state.apply;
        apply.has(key) ? apply.delete(key) : apply.add(key);
    }

    async applyToChart() {
        try {
            this.state.result = await this.orm.call("careos.ai", "careos_apply_note", [this.state.result.id, [...this.state.apply]]);
            this.notification.add("Reviewed sections applied to the chart.", { type: "success" });
            this.env.careos.navigate("encounter", { resId: this.state.context.resId });
        } catch (error) {
            this.notification.add(error.data?.message || "Could not apply to the chart.", { type: "danger" });
        }
    }

    async dismiss() {
        this.state.result = await this.orm.call("careos.ai", "careos_dismiss", [this.state.result.id]);
    }

    async enable() {
        this.state.status = await this.orm.call("careos.ai", "careos_configure", [true, this.state.apiKey || null]);
        this.state.apiKey = "";
        if (this.state.context) {
            await this.run();
        }
    }

    onScrimClick(ev) {
        if (ev.target === ev.currentTarget) {
            this.close();
        }
    }
}

topbarRegistry.add("ai_assistant", { sequence: 60, Component: AiAssistant });
