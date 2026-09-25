import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { EmptyState, LoadingState } from "@careos_base/components/primitives";
import { formatDisplayDate } from "@careos_base/components/format";
import { patientTabRegistry } from "../screens/patient_360";

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

function readAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1]);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

function humanSize(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
        return `${Math.round(bytes / 1024)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export class PatientDocuments extends Component {
    static template = "careos_patients.PatientDocuments";
    static components = { EmptyState, LoadingState };
    static props = { profile: Object, reload: Function };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInput = useRef("fileInput");
        this.state = useState({ documents: null, error: "", uploading: false });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.documents = await this.orm.call("careos.patient", "careos_get_documents", [[this.props.profile.id]]);
        } catch (error) {
            this.state.error = error.data?.message || "Documents could not be loaded.";
        }
    }

    pickFile() {
        this.fileInput.el.click();
    }

    async onFileChosen(ev) {
        const files = [...ev.target.files];
        ev.target.value = "";
        if (!files.length) {
            return;
        }
        this.state.uploading = true;
        try {
            for (const file of files) {
                if (file.size > MAX_UPLOAD_BYTES) {
                    this.notification.add(`${file.name} is larger than 25 MB and was not uploaded.`, { type: "warning" });
                    continue;
                }
                const datas = await readAsBase64(file);
                await this.orm.call("careos.patient", "careos_attach_document", [[this.props.profile.id], file.name, datas]);
            }
            await Promise.all([this.load(), this.props.reload()]);
        } catch (error) {
            this.notification.add(error.data?.message || "The document could not be uploaded.", { type: "danger" });
        } finally {
            this.state.uploading = false;
        }
    }

    downloadUrl(doc) {
        return `/web/content/${doc.id}?download=true`;
    }

    formatDate(value) {
        return formatDisplayDate(value);
    }

    size(doc) {
        return humanSize(doc.size || 0);
    }
}

patientTabRegistry.add("documents", {
    label: "Documents",
    sequence: 20,
    Component: PatientDocuments,
    count: (profile) => profile.document_count,
});
