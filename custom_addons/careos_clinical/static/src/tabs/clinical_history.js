import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Badge, EmptyState, LoadingState } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { patientTabRegistry } from "@careos_patients/screens/patient_360";
import { ENCOUNTER_TONE } from "../clinical_registries";

/** Patient 360 → Clinical history (clinical roles only). */
export class ClinicalHistory extends Component {
    static template = "careos_clinical.ClinicalHistory";
    static components = { Badge, EmptyState, LoadingState };
    static props = { profile: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ rows: null, error: "" });
        onWillStart(async () => {
            try {
                this.state.rows = await this.orm.call("careos.patient", "careos_get_encounters", [[this.props.profile.id]]);
            } catch (error) {
                this.state.error = error.data?.message || "Clinical history could not be loaded.";
            }
        });
    }

    date(row) {
        return formatDisplayDate(row.date);
    }

    tone(row) {
        return ENCOUNTER_TONE[row.state];
    }

    open(row) {
        this.env.careos.navigate("encounter", { resId: row.id });
    }
}

patientTabRegistry.add("clinical", {
    label: "Clinical history",
    sequence: 15,
    Component: ClinicalHistory,
    isVisible: (profile) => profile.encounters_access,
});
