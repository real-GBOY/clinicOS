import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CareModal } from "./modal";

/**
 * Small create form for child records (allergies, contacts, conditions…).
 * The server validates everything; this dialog only checks required fields
 * so the user gets immediate feedback.
 *
 * fields: [{ name, label, type: "char"|"select"|"date"|"textarea"|"boolean",
 *            options?: [[value, label]], required?, placeholder?, wide? }]
 */
export class RecordEntryDialog extends Component {
    static template = "careos_base.RecordEntryDialog";
    static components = { CareModal };
    static props = {
        close: Function,
        title: String,
        model: String,
        fields: Array,
        defaults: { type: Object, optional: true },
        submitLabel: { type: String, optional: true },
        onSaved: { type: Function, optional: true },
    };
    static defaultProps = { submitLabel: "Save" };

    setup() {
        this.orm = useService("orm");
        const values = {};
        for (const field of this.props.fields) {
            values[field.name] = field.type === "boolean" ? Boolean(field.default) : field.default ?? "";
        }
        this.state = useState({ values, errors: {}, serverError: "", saving: false });
    }

    validate() {
        const errors = {};
        for (const field of this.props.fields) {
            const value = this.state.values[field.name];
            if (field.required && (value === "" || value === null || value === undefined)) {
                errors[field.name] = `${field.label} is required`;
            }
        }
        this.state.errors = errors;
        return !Object.keys(errors).length;
    }

    async save() {
        if (this.state.saving || !this.validate()) {
            return;
        }
        this.state.saving = true;
        this.state.serverError = "";
        const vals = { ...(this.props.defaults || {}) };
        for (const field of this.props.fields) {
            const value = this.state.values[field.name];
            vals[field.name] = value === "" ? false : value;
        }
        try {
            const [id] = await this.orm.create(this.props.model, [vals]);
            await this.props.onSaved?.(id);
            this.props.close();
        } catch (error) {
            this.state.serverError = error.data?.message || "The record could not be saved.";
        } finally {
            this.state.saving = false;
        }
    }
}
