import { registry } from "@web/core/registry";

function setValue(selector, value, eventName = "input") {
    const el = document.querySelector(selector);
    el.value = value;
    el.dispatchEvent(new Event(eventName, { bubbles: true }));
}

/** Doctor: workspace → consultation → vitals, notes, diagnosis, prescription, lab → sign-off. */
registry.category("web_tour.tours").add("careos_doctor_visit", {
    steps: () => [
        { content: "Doctor Workspace", trigger: ".co-page-header__title:contains('Doctor Workspace')" },
        {
            content: "Open the patient in consultation",
            trigger: ".co-dashboard__today tr:contains('Farah Tourvisit') button[name='open_visit']",
            run: "click",
        },
        { trigger: ".co-page-header__title:contains('Farah Tourvisit')" },
        { content: "Record vitals", trigger: "button[name='record_vitals']", run: "click" },
        { trigger: ".co-modal input[name='bp_systolic']", run: "edit 128" },
        { trigger: ".co-modal input[name='bp_diastolic']", run: "edit 82" },
        { trigger: ".co-modal input[name='heart_rate']", run: "edit 74" },
        { trigger: ".co-modal button[name='save_vitals']", run: "click" },
        { content: "Vitals on the chart", trigger: ".co-vitals__card[data-vital='bp'] .co-vitals__value:contains('128/82')" },
        { content: "Chief complaint", trigger: "textarea[name='chief_complaint']", run: "edit Headache for three days" },
        { trigger: "textarea[name='notes']", run: "edit Tension-type headache, no red flags." },
        { trigger: ".co-section-label:contains('Diagnosis')", run: "click" },
        { content: "Saved", trigger: ".co-encounter:not(:has(.co-encounter__saving))" },
        { trigger: "input[name='dx_code']", run: "edit G44.2" },
        { trigger: "input[name='dx_description']", run: "edit Tension-type headache" },
        { trigger: "button[name='add_diagnosis']", run: "click" },
        { trigger: ".co-list-row:contains('Tension-type headache')" },
        { content: "Start a prescription", trigger: "button[name='enc_prescription']", run: "click" },
        {
            trigger: ".co-encounter-rx select[name='rx_product']:has(option:contains('Paracetamol'))",
            run() {
                const select = document.querySelector(".co-encounter-rx select[name='rx_product']");
                const option = [...select.options].find((o) => o.textContent.includes("Paracetamol"));
                setValue(".co-encounter-rx select[name='rx_product']", option.value, "change");
            },
        },
        { trigger: "input[name='rx_dose']", run: "edit 500mg" },
        { trigger: "button[name='add_rx_line']", run: "click" },
        { trigger: ".co-encounter-rx td:contains('Paracetamol')" },
        { content: "Issue", trigger: "button[name='rx_issue']", run: "click" },
        { trigger: ".co-encounter-rx .co-badge:contains('Issued')" },
        { content: "Order a lab test", trigger: "button[name='enc_lab_order']", run: "click" },
        { trigger: ".co-modal input[name='test_CBC']", run: "click" },
        { trigger: ".co-modal button[name='place_lab_order']", run: "click" },
        { trigger: ".co-section-label:contains('Lab orders') ~ div:contains('CBC')" },
        { content: "Sign off", trigger: "button[name='complete_encounter']", run: "click" },
        { trigger: ".co-page-header .co-badge:contains('Completed')" },
        { trigger: ".co-alert:contains('Signed off by')" },
    ],
});

/** Patient: portal → message the clinic → request an appointment. */
registry.category("web_tour.tours").add("careos_patient_portal", {
    steps: () => [
        { content: "Portal home", trigger: ".co-portal__title:contains('Welcome back, Farah')" },
        { trigger: ".co-portal__nav-item[data-screen='messages']", run: "click" },
        { trigger: "textarea[name='portal_message']", run: "edit Can I get my results by e-mail?" },
        { trigger: "button[name='portal_send']", run: "click" },
        { content: "Message sent", trigger: ".co-bubble__text:contains('Can I get my results by e-mail?')" },
        { trigger: ".co-portal__nav-item[data-screen='home']", run: "click" },
        { content: "Book new", trigger: "button[name='book_new']", run: "click" },
        {
            content: "Pick tomorrow",
            trigger: ".co-modal input[name='portal_day']",
            run() {
                setValue(".co-modal input[name='portal_day']", luxon.DateTime.now().plus({ days: 1 }).toISODate(), "change");
            },
        },
        { content: "Choose the first free time", trigger: ".co-modal .co-portal__slots button[data-slot]", run: "click" },
        { trigger: "button[name='portal_request']", run: "click" },
        { content: "Requested", trigger: ".co-portal__content .co-badge:contains('Requested')" },
    ],
});
