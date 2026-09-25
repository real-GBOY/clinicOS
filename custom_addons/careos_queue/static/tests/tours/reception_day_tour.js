import { registry } from "@web/core/registry";

const PATIENT = "Nadia Tourtest";

/**
 * A receptionist runs one visit end to end on real records:
 * dashboard → appointment → Patient 360 → check in → queue → call →
 * consultation → complete → Patient 360 timeline. See test_ui.py.
 */
registry.category("web_tour.tours").add("careos_reception_day", {
    steps: () => [
        {
            content: "Reception lands on the dashboard with live counts",
            trigger: ".co-metric[data-kpi='booked'] .co-metric__value:contains('1')",
        },
        {
            content: "Nobody is waiting yet",
            trigger: ".co-metric[data-kpi='waiting'] .co-metric__value:contains('0')",
        },
        {
            content: "Open today's appointment",
            trigger: `.co-dashboard__today tr:contains('${PATIENT}')`,
            run: "click",
        },
        {
            content: "Appointment detail shows it is confirmed",
            trigger: ".co-appointment-detail .co-badge:contains('Confirmed')",
        },
        {
            content: "Go to the patient's record",
            trigger: "button[name='open_patient']",
            run: "click",
        },
        {
            content: "Patient 360 shows the next appointment",
            trigger: `.co-p360__name:contains('${PATIENT}')`,
        },
        {
            content: "Check the patient in from Patient 360",
            trigger: ".co-next-appt button[name='appt_check_in']",
            run: "click",
        },
        {
            content: "The visit is now current and checked in",
            trigger: ".co-next-appt .co-badge:contains('Checked-in')",
        },
        {
            content: "Check-in is on the timeline",
            trigger: ".co-timeline__title:contains('Patient checked in')",
        },
        {
            content: "Open the queue",
            trigger: ".co-sidebar__item[data-screen='queue']",
            run: "click",
        },
        {
            content: "Call the patient",
            trigger: `.co-ticket:contains('${PATIENT}') button[name='ticket_call']`,
            run: "click",
        },
        {
            content: "Start the consultation",
            trigger: `.co-ticket--called:contains('${PATIENT}') button[name='ticket_start']`,
            run: "click",
        },
        {
            content: "Complete the visit",
            trigger: `.co-ticket--consult:contains('${PATIENT}') button[name='ticket_complete']`,
            run: "click",
        },
        {
            content: "The visit is listed as completed today",
            trigger: `.co-ticket--done:contains('${PATIENT}')`,
            run: "click",
        },
        {
            content: "The appointment is completed",
            trigger: ".co-appointment-detail .co-badge:contains('Completed')",
        },
        {
            content: "Back to the patient",
            trigger: "button[name='open_patient']",
            run: "click",
        },
        {
            content: "The Patient 360 timeline tells the whole visit",
            trigger: ".co-timeline__title:contains('Visit completed')",
        },
        {
            trigger: ".co-timeline__title:contains('Patient called')",
        },
        {
            trigger: ".co-timeline__title:contains('Consultation started')",
        },
        {
            content: "Dashboard reflects the completed visit",
            trigger: ".co-sidebar__item[data-screen='dashboard']",
            run: "click",
        },
        {
            trigger: ".co-metric[data-kpi='done'] .co-metric__value:contains('1')",
        },
    ],
});
