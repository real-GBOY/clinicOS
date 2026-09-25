import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { PatientFormDialog } from "../dialogs/patient_form_dialog";

const PAGE_SIZE = 50;
const LIST_FIELDS = ["ref", "name", "age", "date_of_birth", "sex", "phone", "branch_id", "insurance_provider", "create_date", "active"];
const SEX_SHORT = { male: "M", female: "F", other: "O" };

export class PatientDirectory extends Component {
    static template = "careos_patients.PatientDirectory";
    static components = { Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    pageSize = PAGE_SIZE;

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({
            query: "",
            scope: "branch", // "branch" | "all"
            archived: false,
            records: [],
            total: 0,
            offset: 0,
            loading: true,
            error: "",
            canCreate: false,
        });
        this.debouncedLoad = useDebounced(() => this.load(0), 250);
        onWillStart(async () => {
            if (!this.branch) {
                this.state.scope = "all";
            }
            const [canCreate] = await Promise.all([
                this.orm.call("careos.patient", "has_access", [[], "create"]),
                this.load(0),
            ]);
            this.state.canCreate = canCreate;
        });
    }

    get branch() {
        return this.env.careos.session.branch;
    }

    get domain() {
        const domain = [["active", "=", !this.state.archived]];
        const query = this.state.query.trim();
        if (query) {
            domain.push(["display_name", "ilike", query]);
        }
        if (this.state.scope === "branch" && this.branch) {
            domain.push(["branch_id", "=", this.branch.id]);
        }
        return domain;
    }

    async load(offset = this.state.offset) {
        this.state.loading = true;
        this.state.error = "";
        try {
            const { records, length } = await this.orm.webSearchRead("careos.patient", this.domain, {
                specification: Object.fromEntries(
                    LIST_FIELDS.map((f) => [f, f === "branch_id" ? { fields: { display_name: {} } } : {}])
                ),
                offset,
                limit: PAGE_SIZE,
                order: "name asc, id asc",
                context: { active_test: false },
            });
            Object.assign(this.state, { records, total: length, offset });
        } catch (error) {
            this.state.error = error.data?.message || "Patients could not be loaded.";
        } finally {
            this.state.loading = false;
        }
    }

    previousPage() {
        this.load(Math.max(0, this.state.offset - PAGE_SIZE));
    }

    onSearchInput(ev) {
        this.state.query = ev.target.value;
        this.debouncedLoad();
    }

    setScope(scope) {
        this.state.scope = scope;
        this.load(0);
    }

    toggleArchived() {
        this.state.archived = !this.state.archived;
        this.load(0);
    }

    ageSex(record) {
        const age = record.date_of_birth ? `${record.age}` : "—";
        return `${age} / ${SEX_SHORT[record.sex] || "—"}`;
    }

    formatDate(value) {
        return formatDisplayDate(value);
    }

    get rangeLabel() {
        const { offset, records, total } = this.state;
        return total ? `${offset + 1}–${offset + records.length} of ${total}` : "0 patients";
    }

    get subtitle() {
        return this.state.scope === "branch" && this.branch
            ? `Registered at ${this.branch.name}`
            : "All branches in your organization";
    }

    open(record) {
        this.env.careos.navigate("patient", { resId: record.id });
    }

    register() {
        const session = this.env.careos.session;
        this.dialog.add(PatientFormDialog, {
            branches: session.branches,
            defaultBranchId: session.branch?.id || false,
            onSaved: (id) => this.env.careos.navigate("patient", { resId: id }),
            onOpenExisting: (id) => this.env.careos.navigate("patient", { resId: id }),
        });
    }
}

screenRegistry.add("patients", {
    label: "Patients",
    navGroup: "clinical",
    sequence: 10,
    Component: PatientDirectory,
});
