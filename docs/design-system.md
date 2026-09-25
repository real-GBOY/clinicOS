# Design system

Source: "CareOS Brand & Design System" in Claude Design. Implementation:
`careos_base/static/src/scss/tokens.css` (tokens), `components.css` (primitives), `shell.css` (shell).

All tokens are CSS custom properties scoped to `.careos`, so they never alter Odoo's own backend views.
Components reference tokens only — no raw colours in component or screen CSS.

## Tokens

| Group | Tokens |
|---|---|
| Brand | `--careos-primary` `oklch(47% 0.1 195)`, `--careos-primary-hover`, `--careos-primary-soft`, `--careos-chip` |
| Surfaces | `--careos-background`, `--careos-surface`, `--careos-surface-elevated`, `--careos-surface-sunken`, `--careos-border`, `--careos-divider` |
| Text | `--careos-text`, `--careos-text-secondary`, `--careos-muted` |
| Status | `--careos-{success,warning,danger}`, `*-soft`, `*-soft-text`, `--careos-neutral-soft*`, `--careos-secondary-soft*` |
| Navigation | `--careos-nav-bg`, `--careos-nav-item-active`, `--careos-nav-text` |
| Type | Inter throughout; `--careos-text-{display,h1..h4,page-title,body-lg,body,body-sm,caption,button}`; Encode Sans Expanded only for the wordmark |
| Spacing | `--careos-space-{1..8}` (4px base) |
| Radius | `--careos-radius-sm` 6, `--careos-radius` 8, `-lg` 10, `-xl` 12, `-pill` |
| Elevation | `--careos-shadow-sm`, `--careos-shadow`, `--careos-shadow-popover`, `--careos-shadow-modal` |
| Motion | fast 160ms, standard 200ms, overlay 220ms, status 300ms |

Dark mode tokens are defined (`.careos[data-careos-theme="dark"]`) but no toggle ships yet.

## Components

| Component | Where |
|---|---|
| Wordmark, Badge, Avatar, PageHeader, EmptyState, LoadingState, Timeline | `components/primitives.js` |
| CareModal | `components/modal.js` |
| RecordEntryDialog (small create forms) | `components/record_entry_dialog.js` |
| CommandPalette | `search/command_palette.js` |
| CSS-only: `.co-btn*`, `.co-input/select/textarea`, `.co-field*`, `.co-card`, `.co-table*`, `.co-tabs*`, `.co-segmented*`, `.co-popover*`, `.co-alert*`, `.co-kv`, `.co-pagination` | `components.css` |

## Rules carried over from the brand system

* Status is always text + colour (`Badge` requires a label).
* No gradients, glass, or left-border accent cards; 8–10px corners.
* No emoji in product UI (the notification bell is the one planned exception).
* AI output is always labelled "AI-GENERATED · REQUIRES REVIEW" and never writes to a record without a human action.

## Responsive

* ≤ 900px: sidebar becomes an off-canvas drawer (hamburger in the top bar), breadcrumb collapses to the branch.
* ≤ 600px: search collapses to its shortcut chip, forms become one column, modals go full-screen,
  secondary table columns hide (`.co-hide-sm`, `.co-hide-md`).

## Not yet implemented

Date picker (native input for now), toast (Odoo notification service), tooltip, drawer (beyond mobile nav),
metric card component (CSS classes exist), CareOS login page.
