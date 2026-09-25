import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { CareModal } from "@careos_base/components/modal";
import { screenRegistry } from "@careos_base/shell/screen_registry";

const TYPE_FILTERS = [["", "All items"], ["medication", "Medication"], ["supply", "Supplies"], ["lab", "Lab"]];

/** Goods-in: quantity, batch and expiry for one item. */
export class ReceiveStockDialog extends Component {
    static template = "careos_inventory.ReceiveStockDialog";
    static components = { CareModal };
    static props = { close: Function, items: Array, onDone: Function, itemId: { type: Number, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            itemId: String(this.props.itemId || this.props.items[0]?.id || ""),
            quantity: "",
            lot: "",
            expiry: "",
            error: "",
            saving: false,
        });
    }

    async save() {
        this.state.saving = true;
        this.state.error = "";
        try {
            const result = await this.orm.call("careos.inventory", "careos_receive", [
                parseInt(this.state.itemId),
                parseFloat(this.state.quantity),
                this.state.lot || false,
                this.state.expiry || false,
            ]);
            this.props.onDone(result);
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || "Stock could not be received.";
        } finally {
            this.state.saving = false;
        }
    }
}

export class InventoryScreen extends Component {
    static template = "careos_inventory.InventoryScreen";
    static components = { Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.typeFilters = TYPE_FILTERS;
        this.state = useState({ data: null, error: "", query: "", itemType: "" });
        this.debouncedLoad = useDebounced(() => this.load(), 250);
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.data = await this.orm.call("careos.inventory", "careos_overview", [], {
                query: this.state.query,
                item_type: this.state.itemType || false,
            });
            this.state.error = "";
        } catch (error) {
            this.state.error = error.data?.message || "Inventory could not be loaded.";
        }
    }

    onQuery(ev) {
        this.state.query = ev.target.value;
        this.debouncedLoad();
    }

    setType(value) {
        this.state.itemType = value;
        this.load();
    }

    qty(item) {
        return `${item.stock.toLocaleString()}`;
    }

    expiry(item) {
        return item.expiry ? formatDisplayDate(item.expiry) : "—";
    }

    receive(item) {
        this.dialog.add(ReceiveStockDialog, {
            items: this.state.data.items,
            itemId: item?.id,
            onDone: (data) => (this.state.data = data),
        });
    }
}

screenRegistry.add("inventory", {
    label: "Inventory",
    navGroup: "inventory",
    sequence: 10,
    roles: ["pharmacy", "lab", "finance", "manager", "admin"],
    Component: InventoryScreen,
});
