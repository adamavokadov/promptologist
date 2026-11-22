# Ноябрь

## AI-First Design Brief & Design System

- **Version:** 1.0
- **Design baseline:** November 2026
- **Purpose:** Canonical implementation specification for AI agents and frontend teams.

> **Repository notes.** This file is the canonical UI specification of Promptologist. **Part I** (everything up to Addendum A) is the owner's brief «Ноябрь» v1.0: its wording is unchanged, only the Markdown formatting was normalised (tables and lists were reformatted; numeric ranges use an en dash instead of `--`). **Addendum A** (end of file) maps the brief onto this codebase and records project-specific overrides and open decisions. Read both before any UI work. Code status: the redesign is **not implemented yet**; the application still ships the v1.0 neo-glassmorphism UI.

> **Canonical system (2026-11-21): Obsidian / Linear Dark.** Read **Part 0** first. It supersedes the visual values of Part I and Addendum A4; structure, accessibility, engineering and QA rules below still apply.

------------------------------------------------------------------------

## 0. Canonical system: Obsidian / Linear Dark (2026-11-21)

**Status.** This part is the canonical visual system of Promptologist. It supersedes the visual values of Part I (the «Ноябрь» warm light palette, terracotta accent, typography scale, radii, elevation and control skins) and the palette overrides in Addendum A4. Part I and Addendum A still govern structure and process: shell anatomy and responsive behavior, accessibility, engineering rules for AI agents, QA and the definition of done. Where Part 0 and Part I disagree, Part 0 wins. Token values live in `apps/web/src/styles/tokens.css`; `npm run audit:contrast` guards them.

### 0.1 Philosophy
Dark-first, high information density, minimal visual noise, micro-contrast. Layers are separated by 1px borders and small shifts of gray, not by shadows. Neutral zinc scale with a cold undertone and one electric indigo accent. The light theme is a hand-authored sibling with the same structure, not an inversion.

### 0.2 Stack decision
The visual language follows shadcn/ui on Tailwind with Radix-style semantics, **applied through the existing Tailwind and hand-written CSS**. `shadcn/ui` and `@radix-ui/*` packages are **not installed**: the rule "no new dependencies without asking" holds, and nothing in the current screens needs them. Adopting them later is an owner decision. Icons stay Lucide with a global stroke width of 1.75px (CSS `.lucide { stroke-width: 1.75 }`).

### 0.3 Color tokens
Components read only these tokens (no literals). Light is `:root` and `:root[data-theme='light']`; dark is `:root[data-theme='dark']`. `system` sets `data-theme` at runtime from `prefers-color-scheme`. **The default theme is dark** (this supersedes decision D2 of 2026-11-20, which set light); a stored user choice always wins.

| Token | Dark (default) | Light |
|---|---|---|
| `--color-canvas` | `#FAFAFA` | `#FAFAFA` |
| `--color-surface` | `#FFFFFF` | `#FFFFFF` |
| `--color-surface-secondary` | `#F4F4F5` | `#F4F4F5` |
| `--color-elevated` | `#FFFFFF` | `#FFFFFF` |
| `--color-text-primary` | `#09090B` | `#09090B` |
| `--color-text-secondary` | `#52525B` | `#52525B` |
| `--color-text-muted` | `#67676F` | `#67676F` |
| `--color-border` | `#E4E4E7` | `#E4E4E7` |
| `--color-border-strong` | `#D4D4D8` | `#D4D4D8` |
| `--color-control-border` | `#8A8A93` | `#8A8A93` |
| `--color-accent` | `#5E6AD2` | `#5E6AD2` |
| `--color-accent-hover` | `#4F5BC4` | `#4F5BC4` |
| `--color-accent-text` | `#4A55BA` | `#4A55BA` |
| `--color-accent-soft` | `#EEF0FB` | `#EEF0FB` |
| `--color-on-accent` | `#FFFFFF` | `#FFFFFF` |
| `--color-success-text` | `#047857` | `#047857` |
| `--color-success-bg` | `rgba(4, 120, 87, 0.10)` | `rgba(4, 120, 87, 0.10)` |
| `--color-success-border` | `rgba(4, 120, 87, 0.20)` | `rgba(4, 120, 87, 0.20)` |
| `--color-warning` | `#9A4A06` | `#9A4A06` |
| `--color-warning-bg` | `rgba(154, 74, 6, 0.10)` | `rgba(154, 74, 6, 0.10)` |
| `--color-warning-border` | `rgba(154, 74, 6, 0.20)` | `rgba(154, 74, 6, 0.20)` |
| `--color-danger` | `#B91C1C` | `#B91C1C` |
| `--color-danger-bg` | `rgba(185, 28, 28, 0.10)` | `rgba(185, 28, 28, 0.10)` |
| `--color-danger-border` | `rgba(185, 28, 28, 0.20)` | `rgba(185, 28, 28, 0.20)` |
| `--color-info-bg` | `rgba(94, 106, 210, 0.10)` | `rgba(94, 106, 210, 0.10)` |
| `--color-info-border` | `rgba(94, 106, 210, 0.20)` | `rgba(94, 106, 210, 0.20)` |
| `--color-focus` | `var(--color-accent)` | `var(--color-accent)` |
| `--color-scrim` | `rgba(9, 9, 11, 0.40)` | `rgba(9, 9, 11, 0.40)` |
| `--shadow-1` | `0 1px 2px rgba(9, 9, 11, .06), 0 4px 12px rgba(9, 9, 11, .06)` | `0 1px 2px rgba(9, 9, 11, .06), 0 4px 12px rgba(9, 9, 11, .06)` |
| `--shadow-2` | `0 8px 24px rgba(9, 9, 11, .10)` | `0 8px 24px rgba(9, 9, 11, .10)` |

Status badges follow the owner's rule: background at 10% alpha of the status color, border at 20%, text in the status color (`--color-*-bg`, `--color-*-border`, text token). Dark status text is #10B981, #F59E0B, #EF4444 as specified; light status text is darker (#047857, #9A4A06, #B91C1C) to stay at 4.5:1 on the tint.

Mapping of the owner's DESIGN.md names (also defined as aliases in `tokens.css`): `--bg-canvas` = `--color-canvas`, `--bg-surface` = `--color-surface`, `--bg-elevated` = `--color-elevated`, `--border-subtle` = `--color-border`, `--border-strong` = `--color-border-strong`, `--text-primary|secondary|muted` = `--color-text-*`, `--accent-primary` = `--color-accent`, `--accent-hover` = `--color-accent-hover`, `--status-success|warning|error` = `--color-success-text|warning|danger`.

### 0.4 Contrast overrides of the owner's palette (adopted)
| Token | Owner value | Problem (WCAG 2.2 AA) | Adopted |
|---|---|---|---|
| `--text-muted` (dark) | `#71717A` | 4.12:1 on canvas, 3.67:1 on elevated, below 4.5:1 for text | `--color-text-muted` `#8F8F99` |
| `--accent-hover` (dark) | `#6E7BF2` | white label on it is 3.63:1 | `--color-accent-hover` `#4B57C0` (light theme `#4F5BC4`) |
| accent as text | `#5E6AD2` on `#09090B` | 4.23:1 for links and tags | new `--color-accent-text` `#8B93E8` (light `#4A55BA`); the fill `#5E6AD2` stays (white label 4.70:1) |
| input boundaries | `--border-subtle` `#27272A` | about 1.3:1, needs 3:1 for inputs, switches, checkboxes | `--color-control-border` `#71717A` (light `#8A8A93`); decorative dividers keep the subtle border |
| light theme | not specified | needs its own values | table 0.3; muted `#67676F` (`#71717A` is 4.4:1 on `#F4F4F5`); warning `#9A4A06` (`#B45309` is 4.39:1 on its tint) |

### 0.5 Typography, density, shape
Manrope and JetBrains Mono stay (no new font dependency; Inter or Geist is a possible later owner decision). Body 14px, controls and secondary text 13px, meta 12px (nothing smaller), h1 24px, h2 20px, h3 16px, display 32px, metric 32px with tabular numerals. Control height 32px (compact 28px); touch layouts keep 44px tab targets. Radii: 4, 6, 8, 10, 14px (`--radius-sm` to `--radius-2xl`). Spacing scale unchanged (4px base).

### 0.6 Elevation and surfaces
Cards, panels, sidebar and inputs use borders and surface shifts only: canvas, surface (sidebar, cards, panels), elevated (modals, drawers, toasts, menus, hover fills). Shadow tokens exist only for overlays that float above content (`--shadow-1` toast and menus, `--shadow-2` modal and drawer). No gradients, blur or glow.

### 0.7 Components
Primary button: `--color-accent` fill, white label, hover `--color-accent-hover`. Secondary: surface fill, strong border. Ghost: transparent, hover fill. Danger: danger text with the danger border. Focus ring: 2px solid `--color-focus` with 2px offset on every focusable element. Selected nav item and tab: secondary surface fill and weight 600. The primary sidebar action uses the soft accent fill. Disabled controls use muted text and a quiet fill, never reduced opacity.

### 0.8 Data visualization
Indigo ramp `--viz-ramp-1` to `--viz-ramp-5` per theme. Cell text uses whichever of primary text, on-accent or canvas has the highest contrast (the audit enforces at least 4.5:1 for all five steps). The primary series uses `--color-accent`, the comparison series `--viz-series-neutral`. The analytics brief's references to «Ноябрь» tokens now resolve to the values in 0.3; its 28px page title becomes the h1 size in 0.5.

### 0.9 Decisions status
D1 (sidebar), D3 (no stepper), D4 (sticky composer wrapper) and D5 (contrast overrides, now table 0.4) stand. D2 is superseded: dark is the default theme, the switcher stays.

------------------------------------------------------------------------

## 1. Purpose and authority

"Ноябрь" is the canonical design system for the application's research,
document-production and AI workspace. It is the source of truth for
future UI implementation, redesign and extension tasks.

The objective is a modern, premium, AI-native editorial workspace: calm,
spacious, precise, content-first, lightweight and professional.

This brief governs the application shell, navigation, document canvas,
metadata, eight-stage workflow, floating AI composer, controls, design
tokens, interaction states, responsive behavior, accessibility and QA.

Preserve existing business logic, APIs, routes, persisted data, workflow
identifiers, permissions and product functionality. This is a design and
frontend implementation specification, not authorization for a
functional rewrite.

## 2. Core design principles

### Content first

The active document or work artifact is the primary object. Navigation,
metadata, workflow and AI controls support it. Visual priority:

1.  Main document or active artifact.
2.  Current task and required user decision.
3.  AI composer and primary action.
4.  Workflow progress.
5.  Navigation and secondary metadata.

### Open canvas

The workspace must feel like an open working surface, not a stack of
nested cards. Use whitespace to establish hierarchy. Do not wrap every
content area in a card. Avoid heavy document borders, unnecessary
full-width bands and nested backgrounds.

### Quiet visual language

Neutral surfaces dominate. Accent color is reserved for primary actions,
active states and important progress indicators. Status colors
communicate meaning, not decoration.

### Consistency

Use shared tokens and consistent component patterns. Do not invent
one-off colors, spacing, radii or shadows where a token already exists.

### Functional minimalism

Remove visual noise, not useful information. Use progressive disclosure
for secondary details, history and infrequent actions.

## 3. Design direction

**Style name: Minimal Editorial Workspace**

The visual language combines editorial typography, a warm neutral
canvas, compact low-noise navigation, a lightweight workflow indicator
and a distinct floating AI interaction surface.

Avoid traditional enterprise-dashboard styling, excessive nested cards,
thick borders, large shadows, persistent footer panels, strong
gradients, excessive glass effects, oversized controls, decorative
operational illustrations and unnecessary animation.

## 4. Color system

Centralize all colors as semantic design tokens. Do not scatter literal
color values through component styles.

| Token | Hex | Usage |
|---|---|---|
| `--color-canvas` | `#F8F7F4` | Main application and workspace background |
| `--color-surface` | `#FFFFFF` | Composer, menus, popovers and elevated surfaces |
| `--color-surface-secondary` | `#F3F1ED` | Secondary surfaces and hover areas |
| `--color-text-primary` | `#292722` | Main text and headings |
| `--color-text-secondary` | `#77736C` | Secondary text, metadata, completed labels |
| `--color-text-muted` | `#A19B91` | Muted metadata and upcoming states |
| `--color-border` | `#EAE8E3` | Standard borders and separators |
| `--color-border-strong` | `#D8D4CC` | Interactive outlines |
| `--color-accent` | `#C9562D` | Primary actions, active workflow, key emphasis |
| `--color-accent-hover` | `#B94B27` | Accent hover |
| `--color-accent-soft` | `#F6E8E1` | Subtle accent surface |
| `--color-success-bg` | `#E8F1E8` | Success background |
| `--color-success-text` | `#397B4F` | Success text |
| `--color-info-bg` | `#DDE7F0` | Informational background |
| `--color-warning` | `#A45B19` | Pending decision and warning emphasis |
| `--color-warning-bg` | `#F5EBDD` | Subtle warning background |
| `--color-danger` | `#B83A32` | Errors and destructive actions |
| `--color-danger-bg` | `#F7E8E6` | Subtle error background |

### Color rules

-   Use the canvas token for the main workspace.
-   Reserve white for distinct interactive surfaces, especially the
    composer.
-   Keep text contrast readable; subtle must not mean inaccessible.
-   Use accent orange selectively, not for every active or completed
    element.
-   Completed workflow stages use accent fill and a white checkmark.
-   The current stage uses an accent outline and central dot.
-   Upcoming stages use a muted neutral outline.
-   Never communicate status by color alone; pair color with text, icon
    or shape.

The canonical theme is light. If dark mode is implemented, create a
complete semantic token mapping; do not invert colors mechanically.

## 5. Typography

Use one modern neutral sans-serif with strong multilingual support.
Prefer the existing typeface if suitable; otherwise evaluate Inter,
Geist or a suitable system stack. Support Cyrillic, Latin, German and
Portuguese. Avoid unnecessary font-family mixing.

| Role | Size | Weight | Line height |
|---|---|---|---|
| Document title | 36–40px | 600–650 | 1.12–1.2 |
| Major section heading | 23–28px | 600 | 1.2–1.3 |
| Minor heading | 18–21px | 550–600 | 1.3 |
| Body text | 17–18px | 400–450 | 1.55–1.65 |
| Button/control | 14–15px | 500 | 1.3–1.4 |
| Workflow labels | 14–15px | 450–500 | 1.3 |
| Secondary information | 13–14px | 400–500 | 1.35–1.45 |
| Metadata/hints | 12–13px | 400–450 | 1.35–1.45 |

Use restrained weights, comfortable paragraph line-height and consistent
heading spacing. Avoid bold body text, all-caps ordinary labels and
truncation of essential titles without a responsive fallback.

## 6. Spacing and layout tokens

Use a 4px base spacing system.

| Token | Value |
|---|---|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 20px |
| `--space-6` | 24px |
| `--space-7` | 28px |
| `--space-8` | 32px |
| `--space-10` | 40px |
| `--space-12` | 48px |
| `--space-16` | 64px |

| Element | Guideline |
|---|---|
| Desktop sidebar | 270–290px |
| Main document text column | 820–900px |
| Floating composer maximum width | 1050–1150px |
| Composer bottom offset | 20–28px |
| Standard control height | 36–40px |
| Compact control height | 30–34px |
| Workflow circle diameter | 20–22px |
| Workflow connector thickness | 2px |

Treat these as design targets, not fixed values that override responsive
constraints. The main workspace must calculate available width from the
actual sidebar state. Recenter content and composer when the sidebar
collapses.

## 7. Application shell and sidebar

The application consists of a sidebar, main workspace and optional
contextual overlays.

### Sidebar

-   Desktop width: approximately 270–290px.
-   Support collapse/expand where compatible with existing architecture.
-   Use consistent 16–18px icons and compact navigation rows.
-   Use subtle hover backgrounds and restrained active selection.
-   Keep secondary metadata lower in visual hierarchy.
-   Avoid cards around navigation groups and heavy separators.
-   Maintain clear grouping between navigation, document lists and
    utilities.

The primary "New Research" action remains easy to find but must not
dominate the sidebar. Use accent color selectively.

### Document list

Prioritize document title, relevant status, then compact metadata such
as market, language, score and date. Truncate only when necessary;
provide access to the full title through a tooltip or detail view.

## 8. Main workspace and document canvas

The document is the central object.

-   Use `--color-canvas` as the surrounding background.
-   Remove unnecessary outer card borders and shadows.
-   Do not put a heavy card around the entire document.
-   Avoid nested surface containers.
-   Center content in the available workspace.
-   Use approximately 820–900px text width on large desktop screens.
-   Allow natural document scrolling.
-   Keep comfortable whitespace around the document.

Recommended document typography:

-   Title: 36–40px.
-   Body: 17–18px.
-   Body line-height: 1.55–1.65.
-   Paragraph spacing: 16–20px.
-   Text color: `--color-text-primary`.

Preserve author, version, word count, content score, open-full-document,
download-text and all existing document actions. Metadata must remain
secondary to the title and article. Use compact labels; do not wrap
every metadata item in a badge. Use compact text buttons or icon buttons
with tooltips for icon-only actions.

## 9. Eight-stage production workflow

### Canonical visible sequence

1.  Редактура
2.  Проверка
3.  SEO
4.  Оценка
5.  Согласование
6.  Сборка
7.  QA
8.  Публикация

Visible labels may be localized, but order and mapping to existing
backend identifiers must remain unchanged. Do not rename persisted enum
values unless a separate migration explicitly requires it.

### Component concept

Use a minimal horizontal stepper, not a decorative timeline. It must be
compact and visually secondary. On desktop, all eight stages appear in
one row. Do not put stages inside individual cards or pills.

### Completed state

-   Circle diameter: 20–22px.
-   Solid `--color-accent` background.
-   White checkmark, approximately 11–12px.
-   No number inside the circle.
-   Label color: `--color-text-secondary`.
-   Label weight: 450–500.

### Current state

-   Circle diameter: 20–22px.
-   White or canvas-colored fill.
-   2px accent border.
-   Centered accent dot, 6–8px.
-   Label color: `--color-warning` or `--color-accent`.
-   Label weight: 600.
-   Must be immediately recognizable.

### Upcoming state

-   Circle diameter: 20–22px.
-   Transparent or canvas-colored fill.
-   1–1.5px `--color-border-strong` outline.
-   No checkmark and no number.
-   Label color: `--color-text-muted`.
-   Normal label weight.

Do not use a different color for every stage or large numbered circles.

### Connector lines

-   2px thickness.
-   Vertically centered with circles.
-   Completed segments: `--color-accent`.
-   Future segments: `#DEDAD2` or a dedicated muted connector token.
-   Connect circle edges; never draw through circles.
-   No gradients, dotted lines or decorative animation.
-   Derive connector states from actual workflow state.

### Labels

-   14–15px.
-   Completed: `--color-text-secondary`.
-   Current: `--color-warning` or `--color-accent`.
-   Upcoming: `--color-text-muted`.
-   Normal weight: 450–500; current: 600.
-   7–9px gap between indicator and label.
-   Center labels under indicators.
-   Prevent wrapping on desktop. Use a compact responsive mode rather
    than allowing collisions.

### Status context and interaction

A concise status may appear above the stepper, such as "Ожидается ваше
решение", "В работе" or "Проверка завершена". Derive it from workflow
data. Where useful, show position such as "5 из 8". Never hardcode the
current stage.

Where supported:

-   Hover reveals a subtle state and tooltip with stage name/status.
-   Click opens existing stage details or history.
-   Show owner and timestamps only if that data already exists.
-   Do not invent actions.
-   Preserve permissions and disabled-stage behavior.
-   Support keyboard navigation and visible focus.

## 10. Floating AI composer

### Critical visual requirement

The AI composer is an independent floating surface above the document
canvas.

**There must be NO full-width background strip, footer panel, horizontal
divider or visible parent container behind the composer.**

### Positioning

-   Use fixed positioning relative to the viewport or correct workspace
    shell.
-   Anchor 20–28px above the viewport bottom.
-   Center within the main workspace, excluding sidebar width.
-   Maximum width approximately 1050–1150px.
-   Use responsive width.
-   Recalculate position when sidebar collapses or expands.
-   Keep above the scrolling document.
-   Use a correct stacking context and z-index.
-   Avoid clipping caused by ancestor overflow or transforms.
-   Do not hardcode an offset that only works with one sidebar width.

### Appearance

-   Background: `--color-surface`.
-   Border: 1px solid `--color-border-strong` or a softer dedicated
    composer border.
-   Radius: 20–24px.
-   Soft, natural shadow on all sides.
-   Internal padding: 16–20px.
-   No full-width parent background.
-   No heavy backdrop blur.
-   No excessive glassmorphism.

Suggested shadow:

``` css
box-shadow:
  0 4px 16px rgba(40, 35, 28, 0.06),
  0 1px 3px rgba(40, 35, 28, 0.04);
```

### Internal structure

Preserve existing attachment/add button, text input, send action,
keyboard shortcut hint, voice input and secondary controls where
supported. The input is primary; secondary controls remain compact and
visually quieter.

### Scroll relationship

The document scrolls behind the composer. Add sufficient bottom padding
to the document scroll area so the final content can be scrolled fully
above the composer. Do not put the composer in normal document flow if
that creates a footer region or distorts document layout.

### Dynamic states

Verify idle, focused, typing, multiline expansion, loading, disabled,
attachment menu open, voice input active (if supported), narrow viewport
and expanded/collapsed sidebar.

### Reference CSS logic

``` css
.workspace-shell {
  --sidebar-width: 280px;
}

.workspace-main {
  min-width: 0;
  min-height: 100vh;
  background: var(--color-canvas);
}

.workspace-canvas {
  padding-bottom: 180px;
}

.ai-composer {
  position: fixed;
  bottom: 24px;
  left: calc(
    var(--sidebar-width) +
    (100vw - var(--sidebar-width)) / 2
  );
  transform: translateX(-50%);
  width: min(
    1100px,
    calc(100vw - var(--sidebar-width) - 64px)
  );
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: 24px;
  box-shadow:
    0 4px 16px rgba(40, 35, 28, 0.06),
    0 1px 3px rgba(40, 35, 28, 0.04);
  z-index: 100;
}
```

This is conceptual. Adapt it to actual layout architecture, sidebar
state, responsive breakpoints and stacking contexts.

## 11. Buttons, inputs and controls

### Button hierarchy

-   Primary: accent background and white text.
-   Secondary: neutral surface or transparent background with subtle
    border.
-   Tertiary: text-only or icon-only.
-   Destructive: semantic danger styling.

Do not make every button prominent.

### Dimensions

-   Standard height: 36–40px.
-   Compact height: 30–34px.
-   Horizontal padding: 12–16px.
-   Use shared control radius.
-   Icon size: generally 16–18px.
-   Keep labels concise.

### Inputs

Use a white or appropriate neutral surface, subtle border, clear
placeholder, visible focus state and consistent radius. Avoid thick
resting-state outlines.

## 12. Icons, badges and status indicators

Use one consistent icon family. Typical size is 16–18px with consistent
stroke weight. Avoid mixing filled and outlined styles without semantic
reason. Align icons optically with text. Icon-only controls require
accessible names and tooltips.

Use badges sparingly for meaningful states such as success, warning,
error or important document state. Do not turn ordinary metadata into
badges. Avoid bright badge colors and oversized pills.

Communicate status through text plus icon/shape and color. Never rely on
color alone.

## 13. Borders, radii and elevation

### Borders

-   Standard border: 1px.
-   Use `--color-border` for subtle separators.
-   Use `--color-border-strong` for interactive outlines.
-   Avoid outlining every content region.
-   Prefer whitespace when a separator is unnecessary.

### Radius tokens

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 6px | Small controls |
| `--radius-md` | 10px | Standard controls |
| `--radius-lg` | 14px | Menus and small surfaces |
| `--radius-xl` | 18px | Larger panels |
| `--radius-2xl` | 24px | Floating composer |
| `--radius-full` | 9999px | Circles and pills |

### Elevation

-   Level 0: no shadow; canvas and document.
-   Level 1: subtle shadow for popovers and menus.
-   Level 2: soft shadow for composer and important overlays.

Avoid deep, dark shadows.

## 14. Motion and microinteractions

Use motion to communicate state and continuity.

-   Standard transition duration: 150–200ms.
-   Use restrained ease-out for entering and hover feedback.
-   Use appropriate ease-in for dismissing transient surfaces.
-   Allowed: subtle hover, button transitions, focus transitions,
    sidebar collapse, composer expansion, workflow state transitions,
    popover and tooltip appearance.
-   Avoid looping decoration, large scaling, bounce, parallax, delayed
    interaction and motion that disrupts reading.
-   Respect `prefers-reduced-motion`.

## 15. Responsive behavior

Required viewport checks:

-   2048px desktop.
-   1440px desktop.
-   1280px laptop.
-   1024px tablet.
-   768px tablet.
-   390px mobile.

### Desktop

-   Sidebar at standard width.
-   Document centered in available workspace.
-   All eight workflow stages in one row.
-   Composer centered relative to main workspace.

### Tablet

-   Reduce or collapse sidebar as needed.
-   Reduce document margins.
-   Preserve readable document width.
-   Reduce workflow spacing and label size without overlap.
-   Keep composer controls accessible.

### Mobile

-   Use a navigation drawer or compact navigation pattern.
-   Use a compact horizontal scrollable stepper if all eight stages
    cannot fit.
-   Keep current stage visible.
-   Fit composer to viewport with appropriate side margins.
-   Ensure keyboard does not obscure input.
-   Prevent horizontal page overflow.
-   Keep final document content accessible above composer.

Do not simply scale down the desktop layout.

## 16. Accessibility

Target WCAG 2.2 AA where applicable.

-   Sufficient text and control contrast.
-   Keyboard navigation.
-   Visible focus indicators.
-   Accessible names for icon-only controls.
-   Tooltips do not replace accessible labels.
-   Semantic status information.
-   Appropriate button and input semantics.
-   Reduced-motion support.
-   No status conveyed by color alone.
-   No essential information available only on hover.

## 17. Engineering rules for AI agents

Before changes:

1.  Inspect frontend architecture.
2.  Identify components responsible for each visual region.
3.  Inspect CSS variables and theme infrastructure.
4.  Inspect layout, overflow and stacking contexts.
5.  Identify workflow state mapping and backend identifiers.
6.  Identify responsive breakpoints.
7.  Determine which styles are global and component-scoped.

During implementation:

-   Reuse components and state management.
-   Centralize tokens.
-   Avoid duplicated CSS and unnecessary dependencies.
-   Preserve business logic, APIs, routes, data structures, permissions and workflow transitions.
-   Do not hardcode workflow states.
-   Do not use arbitrary one-off values when tokens exist.
-   Do not solve positioning by adding another full-width wrapper.
-   Do not hide overflow or content to conceal defects.
-   Do not remove functionality to simplify visuals.

If architecture conflicts with a requirement, report the conflict and
choose the smallest maintainable change that satisfies the intended
behavior.

## 18. Quality assurance

Run the application and inspect the rendered interface.

### Visual checks

-   Overall hierarchy.
-   Sidebar width and density.
-   Canvas openness.
-   Document typography and readability.
-   Workflow circle and connector alignment.
-   Composer position and shadow.
-   Absence of the full-width bottom strip.
-   Consistent borders, radii and spacing.
-   No unintended horizontal overflow.

### Functional checks

-   Sidebar expanded/collapsed.
-   Document selection and actions.
-   Document scrolling.
-   Workflow state changes.
-   Workflow tooltip and click behavior where supported.
-   Composer focus, typing and multiline expansion.
-   Send action.
-   Attachment and secondary controls.
-   Loading and disabled states.

### Regression checks

-   Browser console.
-   Existing routes.
-   API interactions.
-   Document persistence.
-   Workflow persistence.
-   Keyboard shortcuts.
-   Responsive behavior.

### Screenshot comparison

Capture before-and-after screenshots at 2048px, 1440px, 1280px and
390px. Use them to identify visual regressions, alignment defects and
spacing inconsistencies.

## 19. Definition of done

### Global system

-   [ ] Interface follows Minimal Editorial Workspace direction.
-   [ ] Tokens are centralized.
-   [ ] Color usage is consistent.
-   [ ] Typography hierarchy is consistent.
-   [ ] Spacing follows the 4px scale.
-   [ ] Borders, radii and shadows are consistent.

### Sidebar

-   [ ] Sidebar is compact and visually quiet.
-   [ ] Navigation hierarchy is clear.
-   [ ] Active and hover states are restrained.
-   [ ] Existing functionality is preserved.

### Document canvas

-   [ ] Document is the primary visual object.
-   [ ] Heavy outer card treatment is removed.
-   [ ] Content width and typography are readable.
-   [ ] Metadata is secondary.
-   [ ] Existing actions remain functional.

### Workflow

-   [ ] Eight stages appear in correct order.
-   [ ] Completed, current and upcoming states are distinct.
-   [ ] Circle sizes are consistent.
-   [ ] Checkmarks are centered.
-   [ ] Connector lines are aligned and state-aware.
-   [ ] Labels are readable.
-   [ ] Current stage is immediately recognizable.
-   [ ] Existing workflow logic is preserved.

### Floating composer

-   [ ] Composer is an independent floating surface.
-   [ ] Composer is centered relative to main workspace.
-   [ ] Sidebar width changes are handled.
-   [ ] No full-width parent background is visible.
-   [ ] No footer strip or divider remains behind it.
-   [ ] Document scrolls behind it.
-   [ ] Bottom padding prevents content obstruction.
-   [ ] Composer works at supported viewport sizes.

### Quality

-   [ ] Responsive checks pass.
-   [ ] Accessibility checks are completed.
-   [ ] Existing functionality is preserved.
-   [ ] No new console errors are introduced.
-   [ ] Before-and-after screenshots are provided.

## 20. Required implementation report

When implementation is complete, provide:

1.  Summary of changes.
2.  List of modified files.
3.  Design tokens added or updated.
4.  Description of shell and canvas changes.
5.  Description of workflow stepper implementation.
6.  Description of composer positioning and scroll behavior.
7.  Responsive test results.
8.  Accessibility and regression test results.
9.  Before-and-after screenshots.
10. Remaining issues or deviations.

Do not stop after producing a proposal, mockup or plan. When assigned
implementation work, make changes directly in the existing codebase and
verify the rendered result.

## 21. Final design principle

**The workspace should feel open, calm, intelligent and precise.**

The document is the center of attention. Navigation is quiet. Workflow
progress is clear but compact. The AI composer floats independently
above the canvas. Every visual element has a purpose.

Use whitespace instead of unnecessary containers. Use hierarchy instead
of decoration. Use consistent tokens instead of one-off styling.

**"Ноябрь" is the canonical reference for reproducing this interface in
future development work.**

---

## Addendum A: Promptologist application notes

- **Addendum version:** 1.0 (2026-11-20). Project-specific, not part of Brief v1.0.
- **Precedence:** the Brief governs visual language, tokens, component behavior and QA. This addendum governs how the Brief maps onto this codebase and holds the token overrides in A4. Where it deviates from the Brief it says so and gives the reason.
- **Decisions D1–D5 were resolved on 2026-11-20** (delegated by the owner); see the **Resolved** markers below. The "Also resolved" items: the «Новый промпт» primary action is the Generator entry in the sidebar (no duplicate Generator item), and the Analytics section is admin-only.

### A1. Scope and what must not be invented

The Brief was written for a document-production workspace (documents, an eight-stage article workflow, "New Research"). Promptologist is a prompt generator with seven screens: generator, history, templates, favorites, skills, reports, settings. Anything in the Brief that has no counterpart in this app must not be invented: no fake documents, no fake workflow stages, no attachment or voice controls.

### A2. Mapping of Brief concepts to this app

| Brief concept | Promptologist surface | Notes |
|---|---|---|
| Application shell and sidebar (§7) | `.rail` and `.bottom-tabs` in `apps/web/src/App.tsx` (`NAV`, 7 items) | Keep screen ids and hash routes (`#/generator` and so on). Today: 72px rail that expands to 240px on hover. Target: 270–290px, explicit collapse toggle (see D1). |
| Primary action "New Research" | Generator entry in the sidebar | Only item that may use the accent. Label comes from `strings.ru.ts` (default text: «Новый промпт»). |
| Document canvas (§8) | The active artifact of each screen: generated prompt (Generator, History detail), skill body (Skills), template body (Templates) | Open canvas, no outer card, 820–900px text column. |
| Document title | Screen `h1`. The Generator `h1` («Опишите задачу своими словами») uses the 36–40px title scale; other screens use the 28px major-heading scale | Proposed mapping. |
| Document metadata | Skill version, latency, language, target systems, date | Secondary text. Badges only for meaningful states. |
| Document list | History and Favorites screens | Title is the first line of `raw_input`; then systems, language, date. A recent-items list in the sidebar is optional and not required. |
| Eight-stage workflow (§9) | None | See A5. |
| Floating AI composer (§10) | Generator input surface | See A6. |
| Status badges (§12) | `badge ok/warn/err/info` (skill status, report verdict, agent state) | Re-skin only. Text plus icon or shape plus color. |
| Toasts, modals, drawers | `ToastProvider`, `Modal`, `Drawer`, `ConfirmModal` in `ui.tsx` | Elevation level 1 or 2, no glass, no backdrop blur. |

### A3. Constraints from the existing codebase (must survive the redesign)

- The app runs inside a Bitrix24 iframe and reports its height to the parent with `postMessage({type:'vibe:resize', height})` (`App.tsx`). See conflict C1 in A6.
- `localStorage` access stays wrapped in `try/catch` (blocked storage in iframes). No CDN assets (CSP): fonts stay self-hosted through `@fontsource`.
- Typeface: keep Manrope (Cyrillic and Latin are already bundled), as Brief §5 prefers the existing typeface when suitable. JetBrains Mono stays for prompt text and code only; this is the single allowed exception to "one font family".
- UI strings live only in `apps/web/src/strings.ru.ts`.
- Persisted identifiers are not renamed: screen ids, skill status (`fresh|due|running|failed|paused`), generation status, report verdicts, `Settings.theme` values (`dark|light|system`).
- The helper class API (`btn`, `icon-btn`, `chip`, `badge`, `seg`, `switch`, `tab`, `banner`, `empty`, `modal`, `drawer`, `toast`, `row`, `col`) may be re-skinned in place to limit churn. Removed entirely: `glass`, `aurora`, `noise`, `grid`, `backdrop-filter`, gradient fills, the gradient logo and favicon, the hard-coded star color.
- Theme **Resolved 2026-11-20 (D2):** light is the default theme for users who have no stored choice. The dark/light/system switcher stays and a saved user choice always wins. The hand-authored dark map is in A10. `DEFAULT_SETTINGS.theme` in `shared/src/index.ts` changes from `'dark'` to `'light'` (one line).

### A4. Token overrides from the contrast audit

The Brief targets WCAG 2.2 AA (§16) and says subtle must not mean inaccessible (§4). Several Brief hex values fail that target. Ratios below are computed WCAG contrast ratios. The Brief values stay in Part I as the reference; implementation uses the overrides (**Resolved 2026-11-20 (D5):** all overrides in this table are adopted, including `--color-control-border` for input boundaries, switches and checkboxes).

| Token | Brief | Problem | Override (adopted 2026-11-20) |
|---|---|---|---|
| `--color-text-secondary` | `#77736C` | 4.40 on canvas, 4.18 on surface-secondary (needs 4.5) | `#5F5B54` (6.30 / 5.98) |
| `--color-text-muted` | `#A19B91` | 2.57 on canvas, 2.45 on surface-secondary; fails for text such as upcoming labels, metadata, placeholders | `#716D66` (4.80 / 4.56) |
| `--color-accent` | `#C9562D` | White text on it is 4.33; as text on canvas 4.04 | `#BE4F29` (white 4.84; on canvas 4.52) |
| `--color-accent-hover` | `#B94B27` | none (white 5.12) | unchanged |
| `--color-success-text` | `#397B4F` | 4.41 on success background | `#34734A` (4.92) |
| `--color-warning` | `#A45B19` | 4.36 on warning background (4.79 on canvas is fine) | `#9C5516` (4.78 on warning background) |
| `--color-border-strong` | `#D8D4CC` | 1.38 on canvas; WCAG 1.4.11 asks 3:1 for input boundaries and state indicators | Keep for decoration. Add `--color-control-border: #8C877D` (3.34 on canvas, 3.57 on white) for inputs, selects, switches and the upcoming-stage outline |
| Grok identity dot | `#E5E7EB` | 1.16 on canvas, effectively invisible | Use `--color-text-primary` |

Rules that follow: never place accent-colored text on `--color-accent-soft` (use primary text); the current-stage label uses `--color-warning` or `--color-accent`, both pass on canvas with the overrides; connector lines (`#DEDAD2`) are decorative because stage state is always also given by indicator shape and label. Per-system identity dots (`SYSTEM_COLORS` in `ui.tsx`) move into tokens (`--color-system-claude` and so on); the system name text always accompanies the dot.

### A5. Workflow stepper (Brief §9): no data source in this app

- The labels Редактура … Публикация belong to an article workflow that does not exist here.
- The persisted agent run steps (`refresh_runs.step`: `plan`, `search`, `deep`, `analyze`, `validate`, `golden`, `apply`, then the final report) are not eight stages (`deep` is conditional) and no API or screen exposes them. Generation progress is three transient client states (analyze, transform, done).
- Rule: never wire a stepper to fabricated or hard-coded state (Brief §9, §17).
- **Resolved 2026-11-20 (D3):** the stepper is **not built**. There is no real data source, so no `Stepper` component and no fake stages are created. Options kept for a later decision: (1) skip it entirely; (2) expose agent run steps through a new read-only endpoint and show them in Reports (a business-logic change that needs separate approval); (3) use a compact variant for generation progress. If built, it is a presentational `Stepper` taking `steps: {id, label, state: 'done'|'current'|'upcoming'}[]` computed by the caller, with all Brief §9 visuals and the compact responsive mode.

### A6. Floating composer (Brief §10) and conflict C1

- Applies to the Generator screen only. Contents: textarea (primary), then one compact secondary row with system chips, the RU/EN switch, the advanced-options toggle and the submit button with its `Ctrl+Enter` hint, plus the character counter. Advanced options open as a popover above the composer (elevation level 1). No attachment or voice controls.
- Preserve: validation (`LIMITS.rawInputMin/Max`), loading and disabled states, the keyboard shortcut, prefill from History and Templates, focus handling.
- The clarifying-questions block and the result cards stay on the canvas. Canvas bottom padding is the measured composer height plus twice the bottom offset (set a `--composer-h` variable with a `ResizeObserver`), not a fixed 180px.
- Horizontal position derives from a `--sidebar-width` variable owned by the shell and updated on collapse. In compact mode (under 800px) the composer spans the viewport minus 16px side margins and sits above the bottom tabs and the safe area.
- **Conflict C1 (iframe auto-height).** The app reports its full content height to the Bitrix24 parent. In an auto-height iframe, `position: fixed; bottom` and `100vh` refer to the full-height frame, not to the window the user sees, so the composer would sit at the end of a long page, off screen. Sticky positioning degrades gracefully instead (see D4): the composer floats only where the frame itself scrolls.
- **Resolved 2026-11-20 (D4):** the future Generator composer uses a sticky, transparent wrapper at the bottom of the canvas (`position: sticky; bottom: var(--space-6)`; the wrapper has no background and `pointer-events: none`, the composer itself has `pointer-events: auto`), not `position: fixed`. `vibe:resize` keeps working. In a scrolling iframe the composer floats as in the Brief; in an auto-height iframe it degrades to the end of the content. No host contract is needed. The composer is built in a later task; this item only records the decision.

### A7. Sidebar and breakpoints

- **Resolved 2026-11-20 (D1):** sidebar expanded at 280px from 1024px up, with an explicit collapse toggle to a 64px icon rail (state kept in `localStorage` inside `try/catch`); no hover expansion. From 800 to 1023px the rail starts collapsed. Under 800px the existing bottom tabs with the «Ещё» sheet stay (the Brief allows a compact navigation pattern). The existing `compact` flag (body width under 800px) is kept.

### A8. Implementation map and suggested order

| Area | Files |
|---|---|
| Tokens (light, then dark) | `apps/web/src/index.css` (or a new `styles/tokens.css` imported by it); optionally `tailwind.config.cjs` color mapping |
| Primitives | `ui.tsx` (toasts, modals, drawer, switch, seg, `SYSTEM_COLORS`, `StarButton`), button, chip, badge, input classes in `index.css` |
| Shell | `App.tsx` (sidebar, topbar, background layer removal, logo, theme default), `index.html` (`data-theme`, favicon) |
| Screens | `screens/*.tsx` and `components/ResultCard.tsx`: remove `glass card` wrappers in favor of the open canvas |
| Composer | `screens/Generator.tsx` (after D4) |
| Strings | `strings.ru.ts` |
| Do not touch | `apps/server`, `shared`, `tests`, `scripts`, unless the task says so |

Suggested order: tokens and primitives, shell and sidebar, screen canvases, composer (after D4), QA and report.

### A9. Additions to the definition of done (Brief §19)

- [ ] Contrast overrides from A4 applied and the audit repeated on rendered output.
- [ ] No `glass`, `backdrop-filter`, gradient fill, aurora, noise or grid remains.
- [ ] `npm run build` and `npm test` pass; no server, shared or test files changed unless assigned.
- [x] Decisions D1–D5 resolved on 2026-11-20 and recorded in HANDOFF through `scripts/docs_update.py`; D4 outcome: sticky composer wrapper (A6).
- [ ] Before and after screenshots at 2048, 1440, 1280 and 390px attached to the chat report (not committed unless asked).

### A10. Token values

Superseded on 2026-11-21 by Part 0 §0.3. The source of truth is `apps/web/src/styles/tokens.css` (dark default on `:root[data-theme='dark']`, light on `:root`). The «Ноябрь» values that were listed here are retired.

## Prompt workspace v1.2

The [Prompt workspace specification](docs/prompt-workspace.md) records the default entry flow, routing rules, checklist, compression comparison, prompt fields, role examples and team access decisions for this version.

- Use the existing Obsidian surfaces, spacing, controls and typography for the composer, result and library.
- Keep the primary copy action adjacent to the prompt. Place model commentary, token estimates, prompt execution, external destinations and editing controls in expandable sections.
- Put variable fields above the rendered prompt. Update the preview and copy action from the same value. Keep the original and compressed variant labels visible above the comparison.
- Mark removed text with a strike and added text with an underline. Use the existing muted, danger and success tokens. Show the two alternatives if the diff cannot be calculated within its budget.
- Keep shared folder visibility and user roles explicit in settings. Show a read-only indicator to readers. An editor selects a history entry and saves it as a new revision.
- On narrow screens use the same keyboard-accessible accordions and wrapping grids. Keep the workspace in document flow for the Bitrix24 auto-height iframe.
