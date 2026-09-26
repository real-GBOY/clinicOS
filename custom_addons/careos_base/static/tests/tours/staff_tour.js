import { registry } from "@web/core/registry";

/** Admin: Staff & roles → invite → change roles → deactivate. */
registry.category("web_tour.tours").add("careos_staff_admin", {
    steps: () => [
        { content: "Open Staff & roles", trigger: ".co-sidebar__item[data-screen='staff']", run: "click" },
        { trigger: ".co-page-header__title:contains('Staff & roles')" },
        { content: "Invite", trigger: "button[name='invite_staff']", run: "click" },
        { trigger: ".co-modal input[name='staff_name']", run: "edit Omar Tourdesk" },
        { trigger: ".co-modal input[name='staff_email']", run: "edit omar.tourdesk@example.com" },
        { trigger: ".co-modal input[name='role_reception']", run: "click" },
        { content: "Send", trigger: ".co-modal button[name='save_staff']:not([disabled])", run: "click" },
        { content: "Listed as invited", trigger: "[data-status='invited']", run: "click" },
        { content: "Open the new member", trigger: "tr[data-staff='omar.tourdesk@example.com']", run: "click" },
        { trigger: ".co-modal .co-staff__history:contains('Invited as Reception')" },
        { content: "Add the nurse role", trigger: ".co-modal input[name='role_nurse']", run: "click" },
        { trigger: ".co-modal button[name='save_staff']:not([disabled])", run: "click" },
        { trigger: "tr[data-staff='omar.tourdesk@example.com'] .co-staff__roles:contains('Nurse')" },
        { trigger: "tr[data-staff='omar.tourdesk@example.com']", run: "click" },
        { content: "Deactivate", trigger: ".co-modal button[name='deactivate_staff']", run: "click" },
        { trigger: ".co-modal button[name='reactivate_staff']" },
        { trigger: ".co-modal .co-staff__history:contains('Account deactivated')" },
        { content: "Close", trigger: ".co-modal .co-modal__footer button:contains('Close')", run: "click" },
        { content: "Roles tab", trigger: "button[data-tab='roles']", run: "click" },
        { trigger: ".co-staff__role[data-role='nurse'] .co-staff__caps:contains('Record vitals')" },
    ],
});
