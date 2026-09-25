import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { Badge, EmptyState, LoadingState, PageHeader } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { screenRegistry } from "@careos_base/shell/screen_registry";
import { formatTime } from "@careos_appointments/appointment_utils";
import { ENCOUNTER_TONE } from "../clinical_registries";

const FILTERS = [
    ["open", "In progress", { state: "open" }],
    ["unsigned", "Unsigned", { unsigned: true }],
    ["done", "Completed", { state: "done" }],
    ["all", "All", {}],
];

export class EncounterList extends Component {
    static template = "careos_clinical.EncounterList";
    static components = { Badge, EmptyState, LoadingState, PageHeader };
    static props = { params: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.filters = FILTERS;
        this.state = useState({ filter: "open", query: "", rows: null, error: "" });
        this.debouncedLoad = useDebounced(() => this.load(), 250);
        onWillStart(() => this.load());
    }

    async load() {
        const filter = FILTERS.find((f) => f[0] === this.state.filter)[2];
        try {
            this.state.rows = await this.orm.call("careos.encounter", "careos_list", [], {
                filters: { ...filter, query: this.state.query },
            });
            this.state.error = "";
        } catch (error) {
            this.state.error = error.data?.message || "Encounters could not be loaded.";
        }
    }

    setFilter(key) {
        this.state.filter = key;
        this.load();
    }

    onQuery(ev) {
        this.state.query = ev.target.value;
        this.debouncedLoad();
    }

    when(row) {
        return `${formatDisplayDate(row.date)} · ${formatTime(row.date)}`;
    }

    tone(row) {
        return ENCOUNTER_TONE[row.state];
    }

    open(row) {
        this.env.careos.navigate("encounter", { resId: row.id });
    }
}

screenRegistry.add("encounters", {
    label: "Encounters",
    navGroup: "clinical",
    sequence: 20,
    roles: ["doctor", "nurse"],
    Component: EncounterList,
});
