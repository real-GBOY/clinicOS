import { Component } from "@odoo/owl";

/** CareOS wordmark: lowercase "care" + "os" in the accent chip. */
export class Wordmark extends Component {
    static template = "careos_base.Wordmark";
    static props = { size: { type: Number, optional: true } };
    static defaultProps = { size: 16 };
}

/** Status badge. `tone` maps to the semantic status palette; the label is
 * always rendered so status never relies on colour alone. */
export class Badge extends Component {
    static template = "careos_base.Badge";
    static props = {
        label: String,
        tone: {
            type: String,
            optional: true,
            validate: (t) => ["neutral", "info", "active", "success", "warning", "danger"].includes(t),
        },
    };
    static defaultProps = { tone: "neutral" };
}

export class Avatar extends Component {
    static template = "careos_base.Avatar";
    static props = { name: String, large: { type: Boolean, optional: true } };
    get initials() {
        // Skip titles ("Dr.") and tokens that don't start with a letter.
        const words = (this.props.name || "")
            .split(/\s+/)
            .filter((word) => /^\p{L}/u.test(word) && !word.endsWith("."));
        return words.slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "?";
    }
}

export class PageHeader extends Component {
    static template = "careos_base.PageHeader";
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
}

/** Empty, error and "nothing here yet" states share one component. */
export class EmptyState extends Component {
    static template = "careos_base.EmptyState";
    static props = {
        title: String,
        body: { type: String, optional: true },
        error: { type: Boolean, optional: true },
        slots: { type: Object, optional: true },
    };
}

export class LoadingState extends Component {
    static template = "careos_base.LoadingState";
    static props = { rows: { type: Number, optional: true } };
    static defaultProps = { rows: 4 };
    get rowList() {
        return [...Array(this.props.rows).keys()];
    }
}

/** Vertical timeline. Events: { key, date, title, detail, tone }. */
export class Timeline extends Component {
    static template = "careos_base.Timeline";
    static props = { events: Array };
}
