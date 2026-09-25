import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { sidebarActionRegistry } from "@careos_base/shell/screen_registry";

const STEPS = [
    { key: "organization", title: "Create your organization", desc: "Basic details about your clinic group." },
    { key: "branch", title: "Add your first branch", desc: "You can add more branches later." },
    { key: "departments", title: "Add departments", desc: "Group doctors by specialty." },
    { key: "providers", title: "Add doctors", desc: "Invite doctors and assign specialties." },
    { key: "hours", title: "Configure working hours", desc: "Set default clinic opening hours." },
    { key: "types", title: "Appointment types", desc: "Define bookable visit types and durations." },
    { key: "prices", title: "Services & pricing", desc: "Set prices for consultations and lab tests." },
    { key: "staff", title: "Invite staff", desc: "Add receptionists, nurses, lab and finance users." },
];
const ROLE_LABELS = {
    reception: "Receptionist", doctor: "Doctor", nurse: "Nurse", lab: "Lab technician",
    pharmacy: "Pharmacist", finance: "Finance", manager: "Clinic manager", admin: "Administrator",
};

function hoursToTime(value) {
    const h = Math.floor(value);
    const m = Math.round((value - h) * 60);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function timeToHours(value) {
    const [h, m] = value.split(":").map(Number);
    return h + (m || 0) / 60;
}

/** Prototype "Setup guide · Step N of 8" — every step saves real configuration. */
export class SetupGuide extends Component {
    static template = "careos.SetupGuide";
    static props = { close: Function };

    setup() {
        this.orm = useService("orm");
        this.steps = STEPS;
        this.roleLabels = ROLE_LABELS;
        this.state = useState({ step: 0, s: null, form: {}, error: "", saving: false });
        onWillStart(async () => {
            this.apply(await this.orm.call("careos.setup", "careos_setup_state", []));
        });
    }

    apply(s) {
        this.state.s = s;
        this.state.form = {
            organization: { name: s.organization.name, country_id: String(s.organization.country_id || "") },
            branch: { name: s.branch.name, code: s.branch.code, timezone: s.branch.timezone },
            departments: { text: s.departments.join(", ") },
            providers: { rows: [...s.providers.map((p) => ({ ...p })), { name: "", specialty: "", email: "" }] },
            hours: { days: new Set(s.hours.days), start: hoursToTime(s.hours.start), end: hoursToTime(s.hours.end) },
            types: { rows: [...s.types.map((t) => ({ ...t })), { name: "", duration: 30 }] },
            prices: { types: s.prices.types.map((t) => ({ ...t })), tests: s.prices.tests.map((t) => ({ ...t })) },
            staff: { rows: [{ name: "", email: "", role: "reception" }] },
        };
    }

    get current() {
        return STEPS[this.state.step];
    }

    get f() {
        return this.state.form[this.current.key];
    }

    payload() {
        const key = this.current.key;
        const f = this.f;
        switch (key) {
            case "organization":
                return { name: f.name, country_id: f.country_id ? parseInt(f.country_id) : false };
            case "branch":
                return { name: f.name, code: f.code, timezone: f.timezone };
            case "departments":
                return { names: f.text.split(",") };
            case "providers":
                return { providers: f.rows };
            case "hours":
                return { days: [...f.days], start: timeToHours(f.start), end: timeToHours(f.end) };
            case "types":
                return { types: f.rows };
            case "prices":
                return { types: f.types, tests: f.tests };
            case "staff":
                return { invites: f.rows };
        }
    }

    toggleDay(day) {
        const days = this.f.days;
        days.has(day) ? days.delete(day) : days.add(day);
    }

    addRow(template) {
        this.f.rows.push({ ...template });
    }

    async next() {
        this.state.saving = true;
        this.state.error = "";
        try {
            const s = await this.orm.call("careos.setup", "careos_setup_save", [this.current.key, this.payload()]);
            const step = this.state.step;
            this.apply(s);
            if (step >= STEPS.length - 1) {
                await this.env.careos.reloadSession();
                this.props.close();
                return;
            }
            this.state.step = step + 1;
        } catch (error) {
            this.state.error = error.data?.message || "This step could not be saved.";
        } finally {
            this.state.saving = false;
        }
    }

    back() {
        this.state.step = Math.max(0, this.state.step - 1);
        this.state.error = "";
    }
}

sidebarActionRegistry.add("setup_guide", {
    label: "Setup guide",
    sequence: 10,
    roles: ["admin"],
    style: "filled",
    run: (env) => env.services.dialog.add(SetupGuide, {}),
});
