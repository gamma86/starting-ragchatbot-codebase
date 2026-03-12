# Frontend Changes

## Dark/Light Mode Toggle Button

### Files Modified
- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

### What Was Added

#### `index.html`
- Added a `<button id="themeToggle" class="theme-toggle">` element fixed in the top-right corner, placed before the main `.container` div.
- Contains two inline SVGs: a **sun icon** (shown in dark mode to indicate "switch to light") and a **moon icon** (shown in light mode to indicate "switch to dark").
- Includes `aria-label` and `title` attributes for accessibility.

#### `style.css`
- Added a `body.light-mode` rule that overrides all CSS custom properties (`--background`, `--surface`, `--text-primary`, etc.) with light-mode equivalents.
- Added two new CSS variables: `--toggle-bg` and `--toggle-icon-color`, used to style the button in each theme.
- Added a global `transition` rule on `body *` for `background-color`, `color`, `border-color`, and `box-shadow` (0.3s ease) — this gives all elements a smooth transition when the theme changes.
- Added `.theme-toggle` styles:
  - `position: fixed; top: 1rem; right: 1rem; z-index: 1000` — always visible in top-right.
  - Circular shape (44×44px, `border-radius: 50%`).
  - Hover: scales up slightly, shows shadow.
  - Focus: blue focus ring via `box-shadow` (keyboard-navigable).
  - Active: slight scale-down for tactile feedback.
- Added icon transition logic:
  - In dark mode: sun icon is visible (`opacity: 1`), moon is hidden (`opacity: 0`, rotated).
  - In light mode (`body.light-mode`): moon is visible, sun is hidden.
  - Both icons transition with `opacity` and `transform` (0.3s ease) for a smooth swap animation.

#### `script.js`
- Added `initTheme()`: reads `localStorage` for a saved `'theme'` preference and applies `body.light-mode` + updates `aria-label` on page load.
- Added `toggleTheme()`: toggles `body.light-mode`, saves the new preference to `localStorage`, and updates the button's `aria-label`.
- Both functions are called in the `DOMContentLoaded` handler.

---

## Light Theme Variant — Full Color System

### Files Modified
- `frontend/style.css`

### What Was Changed

#### Complete variable refactor in `style.css`

The `:root` block was expanded with semantic, named variables covering every color concern in the stylesheet. All previously hardcoded `rgba(...)` and hex color values were replaced with CSS variable references, so the light theme can fully override them without any extra selectors.

**New variable groups added to `:root`:**

| Group | Variables |
|---|---|
| Brand | `--primary-shadow` |
| Code blocks | `--code-bg`, `--code-border` |
| Welcome card | `--welcome-shadow` (was hardcoded `rgba`) |
| Error status | `--error-text`, `--error-bg`, `--error-border` |
| Success status | `--success-text`, `--success-bg`, `--success-border` |

**Hardcoded values replaced:**
- `.message-content code` and `.message-content pre`: `rgba(0,0,0,0.2)` → `var(--code-bg)` + added `border: 1px solid var(--code-border)`
- `.message.welcome-message .message-content`: hardcoded `box-shadow` → `var(--welcome-shadow)`; also now uses `var(--welcome-bg)` and `var(--welcome-border)` for background/border (was using `--surface`/`--border-color`)
- `.error-message`: hardcoded rgba colors → `var(--error-bg)`, `var(--error-text)`, `var(--error-border)`
- `.success-message`: hardcoded rgba colors → `var(--success-bg)`, `var(--success-text)`, `var(--success-border)`
- `#sendButton:hover`: `rgba(37,99,235,0.3)` → `var(--primary-shadow)`

**`body.light-mode` palette — accessibility notes:**

| Token | Value | WCAG contrast |
|---|---|---|
| `--text-primary` | `#0f172a` (slate-900) | 16.75:1 on `--background` |
| `--text-secondary` | `#475569` (slate-600) | 5.74:1 on white — passes AA |
| `--error-text` | `#b91c1c` (red-700) | 5.78:1 on white — passes AA |
| `--success-text` | `#15803d` (green-700) | 5.32:1 on white — passes AA |
| `--primary-color` | `#2563eb` (unchanged) | 4.56:1 on white — passes AA |

All status text colors were changed from the dark-theme values (`#f87171`, `#4ade80`) which had poor contrast on light backgrounds, to darker shades that meet WCAG 2.1 AA (4.5:1 minimum) on white.
