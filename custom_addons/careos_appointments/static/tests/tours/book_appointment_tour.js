import { registry } from "@web/core/registry";

function setAndChange(selector, value) {
    const el = document.querySelector(selector);
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

/** Reception books a follow-up from Patient 360. See test_ui.py. */
registry.category("web_tour.tours").add("careos_book_appointment", {
    steps: () => [
        {
            trigger: ".co-sidebar__item[data-screen='patients']",
            run: "click",
        },
        {
            trigger: ".co-patient-directory tr:contains('Omar Booktest')",
            run: "click",
        },
        {
            content: "Nothing booked yet: book from the overview card",
            trigger: ".co-next-appt button[name='book_next']",
            run: "click",
        },
        {
            content: "The patient is prefilled; choose the provider",
            trigger: ".co-modal .co-picker__value:contains('Omar Booktest')",
            run() {
                const select = document.querySelector(".co-modal select[name='provider_id']");
                setAndChange(".co-modal select[name='provider_id']", select.options[1].value);
            },
        },
        {
            content: "Pick tomorrow",
            trigger: ".co-modal input[name='day']",
            run() {
                const tomorrow = luxon.DateTime.now().plus({ days: 1 }).toISODate();
                setAndChange(".co-modal input[name='day']", tomorrow);
            },
        },
        {
            content: "Pick 10:00",
            // Options are not "visible" to the tour engine; wait on the select.
            trigger: ".co-modal select[name='time']:has(option[value='10:00']:not([disabled]))",
            run() {
                setAndChange(".co-modal select[name='time']", "10:00");
            },
        },
        {
            trigger: ".co-modal input[name='reason']",
            run: "edit Blood pressure review",
        },
        {
            trigger: ".co-modal button[name='save_appointment']",
            run: "click",
        },
        {
            content: "The overview now shows the confirmed booking",
            trigger: ".co-next-appt .co-badge:contains('Confirmed')",
        },
        {
            trigger: ".co-next-appt__when:contains('Tomorrow')",
        },
        {
            content: "And the timeline records it",
            trigger: ".co-timeline__title:contains('Appointment confirmed')",
        },
    ],
});
