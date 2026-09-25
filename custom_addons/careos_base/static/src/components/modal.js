import { Component, useExternalListener } from "@odoo/owl";

/**
 * CareOS modal shell. Open it through the dialog service
 * (`dialog.add(MyDialog, props)`): the service passes `close`, and the dialog
 * component renders <CareModal> as its root.
 */
export class CareModal extends Component {
    static template = "careos_base.CareModal";
    static props = {
        title: String,
        close: Function,
        large: { type: Boolean, optional: true },
        slots: Object,
    };

    setup() {
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape") {
                this.props.close();
            }
        });
    }

    onScrimClick(ev) {
        if (ev.target === ev.currentTarget) {
            this.props.close();
        }
    }
}
