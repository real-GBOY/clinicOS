import { queueTicketActionRegistry } from "@careos_queue/screens/queue_board";
import { VitalsDialog } from "./dialogs/vitals_dialog";

queueTicketActionRegistry.add("vitals", {
    label: "Record vitals",
    sequence: 10,
    isVisible: (ticket) => ["waiting", "called"].includes(ticket.state) && ticket.encounter?.can_record_vitals,
    run: (ticket, env, reload) => {
        env.services.dialog.add(VitalsDialog, {
            encounterId: ticket.encounter.id,
            patientName: ticket.patient.name,
            onSaved: reload,
        });
    },
});

queueTicketActionRegistry.add("open_encounter", {
    label: "Open encounter",
    sequence: 20,
    style: "secondary",
    isVisible: (ticket, env) =>
        ["called", "in_consultation"].includes(ticket.state) && ticket.encounter && env.careos.session.roles.includes("doctor"),
    run: (ticket, env) => env.careos.navigate("encounter", { resId: ticket.encounter.id }),
});
