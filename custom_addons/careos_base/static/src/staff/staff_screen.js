import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { Avatar, Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { CareModal } from "@careos_base/components/modal";
import { ROLE_LABELS, screenRegistry } from "@careos_base/shell/screen_registry";

const { DateTime } = luxon;

const STATUS_FILTERS = [["active", "Active"], ["invited", "Invited"], ["inactive", "Deactivated"], ["", "All"]];
const STATUS_BADGES = {
    active: ["Active", "success"],
    invited: ["Invited", "warning"],
    inactive: ["Deactivated", "neutral"],
};

function relative(value) {
    return value ? DateTime.fromSQL(value, { zone: "utc" }).toLocal().toRelative() : "Never";
}

/** Invite a staff member, or edit one's roles, branches and department. */
export class StaffDialog extends Component {
    static template = "careos_base.StaffDialog";
    static components = { Badge, CareModal };
    static props = {
        close: Function,
        overview: Object,
        onDone: Function,
        userId: { type: Number, optional: true },
        defaultBranchId: { type: [Number, { value: false }], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: Boolean(this.props.userId),
            detail: null,
            name: "",
            email: "",
            roles: new Set(),
            branchIds: new Set(this.defaultBranches()),
            branchId: "",
            departmentId: "",
            error: "",
            saving: false,
        });
        onWillStart(async () => {
            if (this.props.userId) {
                this.apply(await this.orm.call("careos.staff", "careos_staff_detail", [this.props.userId]));
            }
        });
    }

    /** New staff start at the inviting admin's current branch. */
    defaultBranches() {
        const branches = this.props.overview.branches;
        if (branches.length === 1) {
            return [branches[0].id];
        }
        return branches.some((b) => b.id === this.props.defaultBranchId) ? [this.props.defaultBranchId] : [];
    }

    apply(detail) {
        Object.assign(this.state, {
            loading: false,
            detail,
            name: detail.name,
            email: detail.email || detail.login,
            roles: new Set(detail.roles),
            branchIds: new Set(detail.branches.map((b) => b.id)),
            branchId: detail.branch_id ? "" + detail.branch_id : "",
            departmentId: detail.department ? "" + detail.department.id : "",
        });
    }

    get isNew() {
        return !this.props.userId;
    }

    get readonly() {
        return !this.props.overview.can_manage || this.state.detail?.status === "inactive";
    }

    get title() {
        return this.isNew ? "Invite staff" : this.state.detail?.name || "Staff member";
    }

    get statusBadge() {
        return STATUS_BADGES[this.state.detail?.status] || STATUS_BADGES.active;
    }

    get selectedBranches() {
        return this.props.overview.branches.filter((b) => this.state.branchIds.has(b.id));
    }

    get departments() {
        return this.props.overview.departments.filter((d) => this.state.branchIds.has(d.branch_id));
    }

    get canSave() {
        return !this.readonly && this.state.name && this.state.email && this.state.roles.size && this.state.branchIds.size;
    }

    lastLogin() {
        return relative(this.state.detail?.last_login);
    }

    when(value) {
        return relative(value);
    }

    toggle(set, value) {
        if (set.has(value)) {
            set.delete(value);
        } else {
            set.add(value);
        }
    }

    toggleBranch(id) {
        this.toggle(this.state.branchIds, id);
        if (this.state.branchId && !this.state.branchIds.has(parseInt(this.state.branchId))) {
            this.state.branchId = "";
        }
        if (this.state.departmentId && !this.departments.some((d) => "" + d.id === this.state.departmentId)) {
            this.state.departmentId = "";
        }
    }

    payload() {
        return {
            name: this.state.name,
            email: this.state.email,
            roles: [...this.state.roles],
            branch_ids: [...this.state.branchIds],
            branch_id: this.state.branchId ? parseInt(this.state.branchId) : false,
            department_id: this.state.departmentId ? parseInt(this.state.departmentId) : false,
        };
    }

    async run(method, args, closeAfter = false) {
        this.state.saving = true;
        this.state.error = "";
        try {
            const detail = await this.orm.call("careos.staff", method, args);
            this.props.onDone();
            if (closeAfter) {
                this.props.close();
            } else {
                this.apply(detail);
            }
        } catch (error) {
            this.state.error = error.data?.message || "The change could not be saved.";
        } finally {
            this.state.saving = false;
        }
    }

    save() {
        if (this.isNew) {
            return this.run("careos_staff_invite", [this.payload()], true);
        }
        return this.run("careos_staff_save", [this.props.userId, this.payload()], true);
    }

    setActive(active) {
        return this.run("careos_staff_set_active", [this.props.userId, active]);
    }

    resend() {
        return this.run("careos_staff_resend_invite", [this.props.userId]);
    }
}

export class StaffScreen extends Component {
    static template = "careos_base.StaffScreen";
    static components = { Avatar, Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.statusFilters = STATUS_FILTERS;
        this.roleLabels = ROLE_LABELS;
        this.state = useState({ data: null, error: "", tab: "staff", query: "", status: "active", role: "" });
        this.debouncedLoad = useDebounced(() => this.load(), 250);
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.data = await this.orm.call("careos.staff", "careos_staff_overview", [], {
                query: this.state.query,
                status: this.state.status,
                role: this.state.role || false,
            });
            this.state.error = "";
        } catch (error) {
            this.state.error = error.data?.message || "Staff could not be loaded.";
        }
    }

    onQuery(ev) {
        this.state.query = ev.target.value;
        this.debouncedLoad();
    }

    setStatus(value) {
        this.state.status = value;
        this.load();
    }

    setRole(value) {
        this.state.role = value;
        this.load();
    }

    showRole(role) {
        Object.assign(this.state, { tab: "staff", role: role.key, status: "active", query: "" });
        this.load();
    }

    statusBadge(member) {
        return STATUS_BADGES[member.status];
    }

    branchNames(member) {
        return member.branches.map((b) => b.name).join(", ") || "—";
    }

    lastLogin(member) {
        return relative(member.last_login);
    }

    open(member) {
        this.dialog.add(StaffDialog, {
            overview: this.state.data,
            userId: member?.id,
            defaultBranchId: this.env.careos.session?.branch?.id || false,
            onDone: () => this.load(),
        });
    }
}

screenRegistry.add("staff", {
    label: "Staff & roles",
    navGroup: "settings",
    sequence: 10,
    roles: ["admin", "manager"],
    Component: StaffScreen,
});
