from odoo import http
from odoo.http import request


class CareosPortalController(http.Controller):
    """The patient portal page and its JSON API. Every call resolves the
    patient from the logged-in user inside ``careos.portal``."""

    @http.route("/careos/portal", type="http", auth="user", website=False)
    def portal_page(self, **kwargs):
        user = request.env.user
        if not user.share:
            # Staff use "View as patient" inside CareOS instead.
            return request.redirect("/odoo/action-careos_base.action_careos_app")
        return request.render("careos_portal.portal_page", {"no_header": True, "no_footer": True})

    def _portal(self):
        return request.env["careos.portal"]

    @http.route("/careos/portal/data", type="jsonrpc", auth="user")
    def data(self):
        return self._portal().careos_portal_data()

    @http.route("/careos/portal/message", type="jsonrpc", auth="user")
    def message(self, text):
        return self._portal().careos_portal_message(text)

    @http.route("/careos/portal/reschedule", type="jsonrpc", auth="user")
    def reschedule(self, appointment_id, note=""):
        return self._portal().careos_portal_reschedule(int(appointment_id), note)

    @http.route("/careos/portal/booking_options", type="jsonrpc", auth="user")
    def booking_options(self, day=None):
        return self._portal().careos_portal_booking_options(day)

    @http.route("/careos/portal/book", type="jsonrpc", auth="user")
    def book(self, provider_id, type_id, start, reason=""):
        return self._portal().careos_portal_book(int(provider_id), int(type_id), start, reason)
