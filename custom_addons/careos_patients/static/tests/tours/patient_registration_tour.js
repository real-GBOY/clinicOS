import { registry } from "@web/core/registry";

/**
 * Reception registers a patient from the directory, lands on the Patient 360,
 * and logs a note. Runs against the real server (see test_ui.py).
 */
registry.category("web_tour.tours").add("careos_patient_registration", {
    steps: () => [
        {
            content: "The CareOS shell is shown, without Odoo's navbar",
            trigger: ".co-shell .co-sidebar__item[data-screen='patients']",
            run: () => {
                const navbar = document.querySelector(".o_main_navbar");
                if (navbar && navbar.offsetParent !== null) {
                    throw new Error("Odoo navbar must not be visible inside CareOS");
                }
            },
        },
        {
            content: "Open the patient directory",
            trigger: ".co-sidebar__item[data-screen='patients']",
            run: "click",
        },
        {
            content: "Open the registration dialog",
            trigger: "button[name='register_patient']",
            run: "click",
        },
        {
            content: "Enter the patient's name",
            trigger: ".co-modal input[name='name']",
            run: "edit Yasmin Tourtest",
        },
        {
            content: "Enter a phone number",
            trigger: ".co-modal input[name='phone']",
            run: "edit +20 100 555 9911",
        },
        {
            content: "Enter the date of birth",
            trigger: ".co-modal input[name='date_of_birth']",
            // The tour "edit" helper cannot drive native date inputs.
            run() {
                const input = document.querySelector(".co-modal input[name='date_of_birth']");
                input.value = "1990-04-12";
                input.dispatchEvent(new Event("input", { bubbles: true }));
            },
        },
        {
            content: "Save",
            trigger: ".co-modal button[name='save_patient']",
            run: "click",
        },
        {
            content: "Patient 360 opens on the new record",
            trigger: ".co-p360__name:contains('Yasmin Tourtest')",
        },
        {
            content: "Registration is on the timeline",
            trigger: ".co-timeline__title:contains('Patient registered')",
        },
        {
            content: "Open the Communication tab",
            trigger: ".co-tabs__tab[data-tab='communication']",
            run: "click",
        },
        {
            content: "Write a note",
            trigger: "textarea[name='note']",
            run: "edit Called to confirm insurance details.",
        },
        {
            content: "Save the note",
            trigger: "button[name='post_note']",
            run: "click",
        },
        {
            content: "The note is listed",
            trigger: ".co-note__body:contains('Called to confirm insurance details.')",
        },
        {
            content: "Global search finds the patient",
            trigger: ".co-topbar__search",
            run: "click",
        },
        {
            trigger: ".co-palette__input",
            run: "edit Yasmin",
        },
        {
            trigger: ".co-palette__result:contains('Yasmin Tourtest')",
        },
    ],
});
