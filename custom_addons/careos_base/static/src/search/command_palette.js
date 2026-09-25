import { Component, onMounted, useExternalListener, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

/**
 * Global search (⌘K / Ctrl+K). Results come from `careos.search`, which runs
 * every query with the user's own access rights.
 */
export class CommandPalette extends Component {
    static template = "careos_base.CommandPalette";
    static props = { close: Function, onSelect: Function };

    setup() {
        this.orm = useService("orm");
        this.inputRef = useRef("input");
        this.state = useState({ query: "", results: [], active: 0, loading: false, error: false });
        this.searchId = 0;
        this.debouncedSearch = useDebounced(() => this.search(), 180);
        onMounted(() => this.inputRef.el.focus());
        useExternalListener(window, "keydown", this.onKeydown.bind(this));
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        if (this.state.query.trim().length < 2) {
            this.state.results = [];
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        this.debouncedSearch();
    }

    async search() {
        const searchId = ++this.searchId;
        try {
            const results = await this.orm.call("careos.search", "careos_global_search", [this.state.query]);
            if (searchId === this.searchId) {
                Object.assign(this.state, { results, active: 0, loading: false, error: false });
            }
        } catch {
            if (searchId === this.searchId) {
                Object.assign(this.state, { results: [], loading: false, error: true });
            }
        }
    }

    onKeydown(ev) {
        const { results } = this.state;
        if (ev.key === "Escape") {
            ev.preventDefault();
            this.props.close();
        } else if (ev.key === "ArrowDown" && results.length) {
            ev.preventDefault();
            this.state.active = (this.state.active + 1) % results.length;
        } else if (ev.key === "ArrowUp" && results.length) {
            ev.preventDefault();
            this.state.active = (this.state.active - 1 + results.length) % results.length;
        } else if (ev.key === "Enter" && results[this.state.active]) {
            ev.preventDefault();
            this.select(results[this.state.active]);
        }
    }

    select(result) {
        this.props.onSelect(result);
        this.props.close();
    }

    onScrimClick(ev) {
        if (ev.target === ev.currentTarget) {
            this.props.close();
        }
    }

    get hint() {
        const { query, loading, error, results } = this.state;
        if (error) {
            return "Search is unavailable right now. Try again in a moment.";
        }
        if (query.trim().length < 2) {
            return "Type at least two characters — name, patient ID, phone or national ID.";
        }
        if (loading) {
            return "Searching…";
        }
        return results.length ? "" : `No results for “${query.trim()}”.`;
    }
}
