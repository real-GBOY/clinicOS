import { Component, onMounted, onWillStart, onWillUnmount, useExternalListener, useState, useSubEnv } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Avatar, EmptyState, Wordmark } from "../components/primitives";
import { CommandPalette } from "../search/command_palette";
import { isScreenAllowed, NAV_GROUPS, ROLE_LABELS, screenRegistry } from "./screen_registry";

/**
 * The CareOS application shell, mounted as a fullscreen client action so no
 * Odoo chrome is shown. It owns navigation, branch context and global search,
 * and renders the active screen from the `careos.screens` registry.
 */
export class CareOSApp extends Component {
    static template = "careos_base.App";
    static components = { Avatar, CommandPalette, EmptyState, Wordmark };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.title = useService("title");
        this.state = useState({
            session: null,
            error: null,
            screen: null,
            params: {},
            pageTitle: "",
            navOpen: false,
            branchMenuOpen: false,
            userMenuOpen: false,
            paletteOpen: false,
            renderKey: 0,
        });

        const shell = this;
        useSubEnv({
            careos: {
                navigate: this.navigate.bind(this),
                setPageTitle: this.setPageTitle.bind(this),
                get session() {
                    return shell.state.session;
                },
            },
        });

        onWillStart(() => this.loadSession());
        // The action manager only switches to fullscreen after this mounts;
        // hide Odoo's navbar immediately so it never flashes inside CareOS.
        onMounted(() => document.body.classList.add("o_careos_active"));
        onWillUnmount(() => document.body.classList.remove("o_careos_active"));

        // Capture phase so Ctrl+K / Cmd+K opens CareOS search, not Odoo's palette.
        useExternalListener(window, "keydown", this.onGlobalKeydown.bind(this), { capture: true });
        useExternalListener(window, "click", this.onWindowClick.bind(this));
    }

    async loadSession() {
        try {
            this.state.session = await this.orm.call("res.users", "careos_get_session_context", []);
        } catch (error) {
            this.state.error = error.data?.message || "CareOS could not be loaded.";
            return;
        }
        const first = this.navScreens[0];
        if (first) {
            this.navigate(first.id);
        }
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------

    get allowedScreens() {
        const roles = this.state.session?.roles || [];
        return screenRegistry
            .getEntries()
            .map(([id, screen]) => ({ id, ...screen }))
            .filter((screen) => isScreenAllowed(screen, roles));
    }

    get navScreens() {
        const order = NAV_GROUPS.map((g) => g.key);
        return this.allowedScreens
            .filter((s) => s.navGroup)
            .sort(
                (a, b) =>
                    order.indexOf(a.navGroup) - order.indexOf(b.navGroup) ||
                    (a.sequence ?? 10) - (b.sequence ?? 10)
            );
    }

    get navGroups() {
        const screens = this.navScreens;
        return NAV_GROUPS.map((group) => ({
            ...group,
            items: screens.filter((s) => s.navGroup === group.key),
        })).filter((group) => group.items.length);
    }

    get currentScreen() {
        return this.allowedScreens.find((s) => s.id === this.state.screen);
    }

    get parentScreen() {
        const parent = this.currentScreen?.parent;
        return parent ? this.allowedScreens.find((s) => s.id === parent) : null;
    }

    get activeNavId() {
        return this.currentScreen?.parent || this.state.screen;
    }

    navigate(screenId, params = {}) {
        const screen = this.allowedScreens.find((s) => s.id === screenId);
        if (!screen) {
            this.notification.add("You don't have access to that workspace.", { type: "warning" });
            return;
        }
        Object.assign(this.state, {
            screen: screenId,
            params,
            pageTitle: screen.label,
            navOpen: false,
            branchMenuOpen: false,
            userMenuOpen: false,
            renderKey: this.state.renderKey + 1,
        });
        this.title.setParts({ action: `${screen.label} · CareOS` });
    }

    setPageTitle(pageTitle) {
        this.state.pageTitle = pageTitle;
        this.title.setParts({ action: `${pageTitle} · CareOS` });
    }

    // ------------------------------------------------------------------
    // Branch context
    // ------------------------------------------------------------------

    toggleBranchMenu(ev) {
        ev.stopPropagation();
        this.state.branchMenuOpen = !this.state.branchMenuOpen;
        this.state.userMenuOpen = false;
    }

    async switchBranch(branch) {
        this.state.branchMenuOpen = false;
        if (branch.id === this.state.session.branch?.id) {
            return;
        }
        this.state.session.branch = await this.orm.call("res.users", "careos_switch_branch", [branch.id]);
        // Remount the screen so it reloads its data for the new branch context.
        this.state.renderKey++;
    }

    // ------------------------------------------------------------------
    // User menu, palette, keyboard
    // ------------------------------------------------------------------

    get roleSummary() {
        const roles = this.state.session?.roles || [];
        return roles.map((r) => ROLE_LABELS[r]).join(", ") || "Staff";
    }

    toggleUserMenu(ev) {
        ev.stopPropagation();
        this.state.userMenuOpen = !this.state.userMenuOpen;
        this.state.branchMenuOpen = false;
    }

    openBackend() {
        browser.location.href = "/odoo";
    }

    logout() {
        browser.location.href = "/web/session/logout";
    }

    openPalette() {
        this.state.paletteOpen = true;
    }

    closePalette() {
        this.state.paletteOpen = false;
    }

    onPaletteSelect(result) {
        this.navigate(result.screen, { resId: result.id });
    }

    onGlobalKeydown(ev) {
        if ((ev.ctrlKey || ev.metaKey) && ev.key?.toLowerCase() === "k") {
            ev.preventDefault();
            ev.stopPropagation();
            this.state.paletteOpen = !this.state.paletteOpen;
        }
    }

    onWindowClick() {
        if (this.state.branchMenuOpen || this.state.userMenuOpen) {
            this.state.branchMenuOpen = false;
            this.state.userMenuOpen = false;
        }
    }

    get searchShortcut() {
        return /Mac|iPhone|iPad/.test(browser.navigator.platform || "") ? "⌘K" : "Ctrl K";
    }
}

registry.category("actions").add("careos.app", CareOSApp);
