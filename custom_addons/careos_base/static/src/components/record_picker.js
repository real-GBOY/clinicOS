import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

/**
 * Typeahead for choosing one record (patient, provider…). Suggestions come
 * from the model's `name_search`, so they follow the user's access rights and
 * the model's `_rec_names_search`.
 */
export class RecordPicker extends Component {
    static template = "careos_base.RecordPicker";
    static props = {
        model: String,
        value: { type: [Object, { value: null }], optional: true }, // { id, display_name }
        onChange: Function,
        domain: { type: Array, optional: true },
        placeholder: { type: String, optional: true },
        name: { type: String, optional: true },
        invalid: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ query: "", results: [], open: false, active: 0 });
        this.debouncedSearch = useDebounced(() => this.search(), 200);
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        this.state.open = true;
        this.debouncedSearch();
    }

    async search() {
        const query = this.state.query.trim();
        if (!query) {
            this.state.results = [];
            return;
        }
        const results = await this.orm.call(this.props.model, "name_search", [], {
            name: query,
            domain: this.props.domain || [],
            limit: 8,
        });
        this.state.results = results.map(([id, display_name]) => ({ id, display_name }));
        this.state.active = 0;
    }

    select(record) {
        Object.assign(this.state, { query: "", results: [], open: false });
        this.props.onChange(record);
    }

    clear() {
        this.props.onChange(null);
    }

    onKeydown(ev) {
        const { results } = this.state;
        if (ev.key === "ArrowDown" && results.length) {
            ev.preventDefault();
            this.state.active = (this.state.active + 1) % results.length;
        } else if (ev.key === "ArrowUp" && results.length) {
            ev.preventDefault();
            this.state.active = (this.state.active - 1 + results.length) % results.length;
        } else if (ev.key === "Enter" && results[this.state.active]) {
            ev.preventDefault();
            this.select(results[this.state.active]);
        } else if (ev.key === "Escape" && this.state.open) {
            ev.stopPropagation();
            this.state.open = false;
        }
    }

    onBlur() {
        // Let a click on a suggestion land before closing.
        setTimeout(() => (this.state.open = false), 150);
    }
}
