"""CareOS authorization helpers.

Every public ``careos_*`` method follows the same order (see docs/architecture.md,
"Authorization pipeline"):

1. ACLs and record rules (Odoo, automatic for non-sudo access)
2. validate arguments and resolve records in the caller's scope
3. ``require_role`` when the operation is role-specific
4. business invariants (state machine, validations)
5. ``sudo()`` only after 1-4, and only for the narrow read or write that needs it

Role sets belong to the domain module that owns the operation (e.g.
``BILL_ROLES`` in careos_finance); this module only evaluates them, so every
check behaves the same way.
"""

from odoo.exceptions import AccessError


def user_roles(env):
    """CareOS role keys of the current user (see ``CAREOS_ROLES``)."""
    return set(env.user._careos_role_keys())


def has_role(env, allowed):
    """True if the current user holds one of ``allowed`` role keys.

    The superuser (internal jobs, demo loading) always passes; Odoo system
    administrators count as CareOS administrators.
    """
    if env.su:
        return True
    allowed = {allowed} if isinstance(allowed, str) else set(allowed)
    if allowed & user_roles(env):
        return True
    return "admin" in allowed and env.user.has_group("base.group_system")


def require_role(env, allowed, message=None):
    """Raise ``AccessError`` unless ``has_role(env, allowed)``."""
    if not has_role(env, allowed):
        raise AccessError(message or env._("Your role does not allow this action."))
