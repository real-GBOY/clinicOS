import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { CareModal } from "@careos_base/components/modal";
import { formatDisplayDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { appointmentSectionRegistry } from "@careos_appointments/screens/appointment_detail";
import { patientTabRegistry } from "@careos_patients/screens/patient_360";

export function money(amount, currency) {
    const value = Number(amount || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
    return `${value} ${currency || ""}`.trim();
}

/** Record a payment against an invoice. */
export class PaymentDialog extends Component {
    static template = "careos_finance.PaymentDialog";
    static components = { CareModal };
    static props = { close: Function, invoice: Object, onDone: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ amount: String(this.props.invoice.balance), method: "cash", error: "", saving: false });
    }

    money(value) {
        return money(value, this.props.invoice.currency);
    }

    async save() {
        this.state.saving = true;
        this.state.error = "";
        try {
            const detail = await this.orm.call("careos.billing", "careos_register_payment",
                [this.props.invoice.id, parseFloat(this.state.amount), this.state.method]);
            await this.props.onDone(detail);
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || "The payment could not be recorded.";
        } finally {
            this.state.saving = false;
        }
    }
}

export class RefundDialog extends Component {
    static template = "careos_finance.RefundDialog";
    static components = { CareModal };
    static props = { close: Function, invoice: Object, onDone: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ reason: "", error: "", saving: false });
    }

    async save() {
        this.state.saving = true;
        try {
            const detail = await this.orm.call("careos.billing", "careos_refund", [this.props.invoice.id, this.state.reason]);
            await this.props.onDone(detail);
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || "The refund could not be issued.";
        } finally {
            this.state.saving = false;
        }
    }
}

/** Prototype "Invoice INV-2026-0917". */
export class InvoiceDetail extends Component {
    static template = "careos_finance.InvoiceDetail";
    static components = { Badge, EmptyState, LoadingState };
    static props = { params: Object };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ inv: null, error: "", busy: false });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.apply(await this.orm.call("careos.billing", "careos_invoice_detail", [this.props.params.resId]));
        } catch (error) {
            this.state.error = error.data?.message || "This invoice could not be opened.";
        }
    }

    apply(inv) {
        this.state.inv = inv;
        this.env.careos.setPageTitle(inv.name);
    }

    money(value) {
        return money(value, this.state.inv.currency);
    }

    date(value) {
        return formatDisplayDate(value);
    }

    async post() {
        this.state.busy = true;
        try {
            this.apply(await this.orm.call("careos.billing", "careos_post", [this.state.inv.id]));
        } catch (error) {
            this.notification.add(error.data?.message || "The invoice could not be issued.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    pay() {
        this.dialog.add(PaymentDialog, { invoice: this.state.inv, onDone: (detail) => this.apply(detail) });
    }

    refund() {
        this.dialog.add(RefundDialog, { invoice: this.state.inv, onDone: (detail) => this.apply(detail) });
    }

    openPatient() {
        this.env.careos.navigate("patient", { resId: this.state.inv.patient.id });
    }
}

export class InvoiceList extends Component {
    static template = "careos_finance.InvoiceList";
    static components = { Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.filters = [["unpaid", "Unpaid"], ["paid", "Paid"], ["draft", "Draft"], ["", "All"]];
        this.state = useState({ status: "unpaid", query: "", rows: null, error: "" });
        this.debouncedLoad = useDebounced(() => this.load(), 250);
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.rows = await this.orm.call("careos.billing", "careos_invoice_list", [], {
                status: this.state.status || false,
                query: this.state.query,
            });
        } catch (error) {
            this.state.error = error.data?.message || "Invoices could not be loaded.";
        }
    }

    setFilter(value) {
        this.state.status = value;
        this.load();
    }

    onQuery(ev) {
        this.state.query = ev.target.value;
        this.debouncedLoad();
    }

    money(row, value) {
        return money(value, row.currency);
    }

    date(row) {
        return row.date ? formatDisplayDate(row.date) : "—";
    }

    open(row) {
        this.env.careos.navigate("invoice", { resId: row.id });
    }
}

/** Appointment detail → Billing card: create the visit invoice. */
export class VisitBilling extends Component {
    static template = "careos_finance.VisitBilling";
    static components = { Badge };
    static props = { appointment: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ data: null, busy: false });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.data = await this.orm.call("careos.billing", "careos_visit_billing", [this.props.appointment.id]);
        } catch {
            this.state.data = null;
        }
    }

    money(value) {
        return money(value, this.state.data.currency);
    }

    async createInvoice() {
        this.state.busy = true;
        try {
            const moveId = await this.orm.call("careos.billing", "careos_create_invoice", [this.props.appointment.id]);
            this.env.careos.navigate("invoice", { resId: moveId });
        } catch (error) {
            this.notification.add(error.data?.message || "The invoice could not be created.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    open(invoice) {
        this.env.careos.navigate("invoice", { resId: invoice.id });
    }
}

/** Patient 360 → Billing (prototype tab). */
export class PatientBilling extends Component {
    static template = "careos_finance.PatientBilling";
    static components = { Badge, EmptyState, LoadingState };
    static props = { profile: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ rows: null, error: "" });
        onWillStart(async () => {
            try {
                this.state.rows = await this.orm.call("careos.billing", "careos_patient_invoices", [this.props.profile.id]);
            } catch (error) {
                this.state.error = error.data?.message || "Billing could not be loaded.";
            }
        });
    }

    money(row, value) {
        return money(value, row.currency);
    }

    get balanceDue() {
        return money(this.props.profile.balance_due, this.props.profile.currency);
    }

    date(row) {
        return row.date ? formatDisplayDate(row.date) : "—";
    }

    open(row) {
        this.env.careos.navigate("invoice", { resId: row.id });
    }
}

screenRegistry.add("invoices", {
    label: "Invoices",
    navGroup: "finance",
    sequence: 10,
    roles: ["reception", "finance", "manager", "admin"],
    Component: InvoiceList,
});
screenRegistry.add("invoice", {
    label: "Invoice",
    parent: "invoices",
    roles: ["reception", "finance", "manager", "admin"],
    Component: InvoiceDetail,
});
appointmentSectionRegistry.add("billing", {
    sequence: 10,
    Component: VisitBilling,
    isVisible: (appointment, env) =>
        ["done", "in_progress"].includes(appointment.state) &&
        env.careos.session.roles.some((r) => ["reception", "finance", "manager", "admin"].includes(r)),
});
patientTabRegistry.add("billing", {
    label: "Billing",
    sequence: 40,
    Component: PatientBilling,
    isVisible: (profile) => profile.billing_access,
});
