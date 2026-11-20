#!/usr/bin/env python3
"""Patch 2026-11-20: «Ноябрь» design system docs, agents.md, Claude project instructions.

Run from the repo root (idempotent, stdlib only, two-phase: everything is validated in memory first,
nothing is written if any anchor is missing):

    python3 patch_2026-11-20_design-system-docs.py --dry-run --diff   # preview
    python3 patch_2026-11-20_design-system-docs.py                    # apply (backups in .patch-backup/)
    python3 patch_2026-11-20_design-system-docs.py --commit           # apply + git add/commit

What it does:
  1. Adds design.md (owner's brief «Ноябрь» v1.0 + Addendum A for this app), agents.md, CLAUDE.md
     (imports agents.md for Claude Code) and docs/claude-project-instructions.md.
  2. README: project documents section; excludes root patch_*.py from repomix packs.
  3. Removes placeholder entries ("...", "id: summary") that running the docs tool usage examples
     verbatim wrote into CHANGELOG.md and HANDOFF.md.
  4. Records the change in CHANGELOG.md / HANDOFF.md through scripts/docs_update.py.

Existing files with different content are never overwritten unless --force-docs is given.
No application code is changed: the UI redesign itself is a separate task driven by design.md.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys

PATCH_ID = "2026-11-20-design-system-docs"
PATCH_DATE = "2026-11-20"

NEW_FILES = {
    "design.md": r'''# Ноябрь

## AI-First Design Brief & Design System

- **Version:** 1.0
- **Design baseline:** November 2026
- **Purpose:** Canonical implementation specification for AI agents and frontend teams.

> **Repository notes.** This file is the canonical UI specification of Promptologist. **Part I** (everything up to Addendum A) is the owner's brief «Ноябрь» v1.0: its wording is unchanged, only the Markdown formatting was normalised (tables and lists were reformatted; numeric ranges use an en dash instead of `--`). **Addendum A** (end of file) maps the brief onto this codebase and records project-specific overrides and open decisions. Read both before any UI work. Code status: the redesign is **not implemented yet**; the application still ships the v1.0 neo-glassmorphism UI.

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
- **[Decision] items** need the owner's confirmation. Until then, use the stated default and list the item in the implementation report (Brief §20).

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
- Theme **[Decision D2]**: the canonical theme is light. Default: light for new users; keep the dark/light/system switcher; a user's stored choice is respected. Dark needs a complete hand-authored token map (Brief §4: no mechanical inversion) that is added to this file when written. Changing the persisted default `theme: 'dark'` in `shared/src/index.ts` needs owner approval.

### A4. Token overrides from the contrast audit

The Brief targets WCAG 2.2 AA (§16) and says subtle must not mean inaccessible (§4). Several Brief hex values fail that target. Ratios below are computed WCAG contrast ratios. The Brief values stay in Part I as the reference; implementation uses the overrides once the owner confirms (**[Decision D5]**).

| Token | Brief | Problem | Override |
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
- **[Decision D3]** Default: the stepper is **not built** in the first implementation pass. Options for the owner: (1) skip it entirely; (2) expose agent run steps through a new read-only endpoint and show them in Reports (a business-logic change that needs separate approval); (3) use a compact variant for generation progress. If built, it is a presentational `Stepper` taking `steps: {id, label, state: 'done'|'current'|'upcoming'}[]` computed by the caller, with all Brief §9 visuals and the compact responsive mode.

### A6. Floating composer (Brief §10) and conflict C1

- Applies to the Generator screen only. Contents: textarea (primary), then one compact secondary row with system chips, the RU/EN switch, the advanced-options toggle and the submit button with its `Ctrl+Enter` hint, plus the character counter. Advanced options open as a popover above the composer (elevation level 1). No attachment or voice controls.
- Preserve: validation (`LIMITS.rawInputMin/Max`), loading and disabled states, the keyboard shortcut, prefill from History and Templates, focus handling.
- The clarifying-questions block and the result cards stay on the canvas. Canvas bottom padding is the measured composer height plus twice the bottom offset (set a `--composer-h` variable with a `ResizeObserver`), not a fixed 180px.
- Horizontal position derives from a `--sidebar-width` variable owned by the shell and updated on collapse. In compact mode (under 800px) the composer spans the viewport minus 16px side margins and sits above the bottom tabs and the safe area.
- **Conflict C1 (iframe auto-height).** The app reports its full content height to the Bitrix24 parent. In an auto-height iframe, `position: fixed; bottom` and `100vh` refer to the full-height frame, not to the window the user sees, so the composer would sit at the end of a long page, off screen. Sticky positioning fails the same way because the parent page scrolls, not the iframe.
- **[Decision D4]** Resolve before building the composer; all other parts of the redesign can proceed without it. Ask the owner whether the placement iframe has a fixed height. If yes: make the shell `height: 100dvh` with internal scroll in the canvas, stop reporting oversized `vibe:resize` heights, and use the fixed composer from the Brief. If no: render the composer in flow at the end of the canvas as an independent, centered surface with no band or divider, and record this as a deviation. Never fix it with an extra full-width wrapper or by hiding overflow (Brief §17). Test inside a real Bitrix24 placement or a local iframe harness that listens for `vibe:resize`, not only in standalone Vite.

### A7. Sidebar and breakpoints

- **[Decision D1]** Default: sidebar expanded at 280px from 1024px up, with an explicit collapse toggle to a 64px icon rail (state kept in `localStorage` inside `try/catch`); no hover expansion. From 800 to 1023px the rail starts collapsed. Under 800px the existing bottom tabs with the «Ещё» sheet stay (the Brief allows a compact navigation pattern). The existing `compact` flag (body width under 800px) is kept.

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
- [ ] Decisions D1–D5 answered or the used defaults listed in the report; C1 outcome recorded in HANDOFF through `scripts/docs_update.py`.
- [ ] Before and after screenshots at 2048, 1440, 1280 and 390px attached to the chat report (not committed unless asked).
''',
    "agents.md": r'''# agents.md: operating manual for AI agents

Read this first. Deep reference: `HANDOFF.md` (architecture, API, data model, decisions, open risks). UI work: `design.md` is mandatory. Runbook: `OPERATIONS.md`. Release history: `CHANGELOG.md`.

## 1. Project

Promptolog («Промптолог»): a web app inside Bitrix24 on the Alaio Vibecode platform. The user writes a raw idea; the app returns a structured prompt per target AI system (Claude, ChatGPT, Kimi, Qwen, Grok) in RU or EN. Each system has a versioned **skill** (Markdown); a built-in **agent** refreshes each skill every 10–15 days from whitelisted official sources, with golden tests, a canary and auto-rollback.

The owner works in GitHub Codespaces and deploys by himself. Agents produce source and patches only: no deployment, no real keys.

## 2. Stack and layout

- Node >= 22.5 (devcontainer: 24), TypeScript strict, Fastify 5, `node:sqlite`, zod 4. React 18, Vite, Tailwind 3 with a hand-written design system in `index.css`, lucide-react, marked + DOMPurify. Tests: vitest.
- `shared/src/index.ts`: constants, zod schemas, DTO types. `apps/server/src/*`: backend. `apps/web/src/*`: `App.tsx` (shell), `ui.tsx` (primitives), `strings.ru.ts` (all UI strings), `index.css`, `screens/*`, `components/*`. `scripts/`, `tests/`, `patches/` (archived patch scripts).

## 3. Commands

```
npm ci
npm run typecheck
npm run build                     # typecheck + vite build + esbuild
npm test
DEV_AUTH_BYPASS=1 DATA_DIR=./data npm run dev:server     # :3000 (bypass ignored in production)
npm run dev:web                                           # :5173, proxies /api to :3000
node scripts/smoke.mjs --base http://127.0.0.1:3000
npm run pack:repomix              # refresh repomix-output.xml
```

## 4. Language policy

- Think, write code, comments, commits and docs in English.
- App UI strings are Russian and live only in `apps/web/src/strings.ru.ts`.
- Reports and chat replies to the owner are in Russian.

## 5. Hard rules

1. `CHANGELOG.md` and `HANDOFF.md` are changed only through `scripts/docs_update.py` (`npm run docs:*`), never by hand. Never run its usage examples verbatim: the placeholders (`...`, `id: summary`) get written into the files. Use `--dry-run` first.
2. Deliver changes as ONE Python patch script plus Codespaces commands (sections 7 and 8). Loose snippets only when the owner asks.
3. Preserve business logic, API routes, persisted data and enum values, permissions. UI tasks do not touch `apps/server`, `shared` or `tests` unless the task says so.
4. No UI strings outside `strings.ru.ts`. No colors, spacing, radii or shadows outside design tokens.
5. Never print or commit secrets. Use `REPLACE_WITH_…` placeholders. Do not invent platform API contracts: unverified ones are listed in `HANDOFF.md` section 10.
6. No new dependency without approval (state why and the size). No CDN assets: CSP and the iframe forbid them. Keep `package-lock.json` committed (repomix omits it).
7. Do not hide defects: no `overflow: hidden` to mask a layout bug, no extra wrapper hacks (`design.md` §17).
8. Report a conflict between a requirement and the architecture early. Take the smallest maintainable change. Ask at most one question, and only if blocked; otherwise state the assumption and proceed.
9. `localStorage` is always wrapped in `try/catch` (blocked in iframes). SQL only through prepared statements. zod validates every input.

## 6. Design system

Before any UI task read `design.md` fully: Part I is the «Ноябрь» brief (light canvas, warm neutrals, one terracotta accent, floating composer); Addendum A maps it onto this app, holds the contrast-based token overrides, and lists open **[Decision]** items (D1–D5). Use the stated defaults for undecided items and list them in the report. The redesign is not implemented yet: the code still ships the v1.0 glassmorphism UI.

## 7. Patch-script standard

File `patch_<YYYY-MM-DD>_<slug>.py` in the repo root. Python 3.12, stdlib only.

- Docstring with usage; `PATCH_ID` and `PATCH_DATE` constants.
- `find_root()` checks `package.json` name is `promptolog`.
- Two-phase: build the whole plan in memory, validate every anchor, write nothing if any check fails.
- Idempotent: a re-run prints "Nothing to do". Anchors use `replace_once(rel, old, new, marker)`. New files never overwrite existing ones unless explicitly forced.
- LF newlines. Backups to `.patch-backup/<PATCH_ID>/`. Flags: `--dry-run`, `--diff`, `--commit`, `--no-backup`, `--root`.
- Docs go through `scripts/docs_update.py` functions. The script archives itself to `patches/`.
- Validate `package.json` stays valid JSON after edits.
- Test the script on a clean copy of the repo (dry-run, apply, re-apply) before handing it over, and say what could not be run.

## 8. Codespaces activation

```
cd /workspaces/<repo>
python3 patch_<id>.py --dry-run --diff
python3 patch_<id>.py
npm ci && npm run build && npm test
git status && git add -A && git commit -m "<type>: <imperative summary>"
npm run pack:repomix
```

Commit style: imperative, with a type prefix (`feat:`, `fix:`, `style:`, `docs:`, `chore:`). Legacy phase commits looked like `phase 4: ...`.

## 9. Workflow for every task

1. Read the task, the relevant `HANDOFF.md` sections and the actual files. Never assume a file's content; if it is not in the pack or the repo, say so and ask for it.
2. State assumptions in one to three lines.
3. Implement the smallest change that satisfies the intent. No stubs in working scenarios.
4. Verify: `typecheck`, `build`, `test`; for UI also run the app and inspect it (section 10).
5. Record the change through `docs_update.py`: changelog entries under `[Unreleased]`; handoff decisions, limitations and the patch log.
6. Report to the owner (section 12).

## 10. UI QA (design.md §18)

- Run `dev:server` and `dev:web`; inspect the rendered result, not only the code.
- Screenshots before and after at 2048, 1440, 1280 and 390px (add 1024 and 768 for responsive checks). Playwright through `npx --yes playwright` is fine ad hoc; do not add it to `package.json` without approval. Keep screenshots out of the repo.
- Test the iframe behavior with a local harness page that embeds the app and listens for `vibe:resize` (see `design.md` A6, conflict C1).
- Check: console errors, keyboard navigation and visible focus, reduced motion, no horizontal overflow, contrast of rendered text, and unchanged routes and API calls.

## 11. Definition of done

- Build and tests pass; no unrelated files changed; docs updated through the tool.
- UI tasks: `design.md` §19 checklist plus Addendum A9.
- Patch scripts: tested as in section 7.

## 12. Report format (to the owner, in Russian, short)

1. Что сделано. 2. Файлы. 3. Как проверено (команды и результат; что не удалось запустить). 4. Отклонения, решения по умолчанию, риски. 5. Команды для Codespaces.

## 13. Known traps

- Seed templates are inserted by title at start; template `language` supports only `ru|en`.
- Deleting a generation hides its favourites too (soft delete is a full removal from all views).
- `DEV_AUTH_BYPASS=1` works only when `NODE_ENV` is not `production`.
- The app lives in an auto-height iframe: `position: fixed` and `100vh` do not behave like in a normal page (conflict C1 in `design.md`).
- TypeScript 7 and Vite 8 versions are pinned by the lockfile; use `npm ci`, not `npm install`, for reproducible builds.
- `repomix-output.xml` is a read-only snapshot and may be stale.
''',
    "CLAUDE.md": r'''# CLAUDE.md

@agents.md

UI work: read design.md before touching apps/web.
''',
    "docs/claude-project-instructions.md": r'''# Claude Project custom instructions: Promptolog

Paste everything below the line into the Project's custom instructions. Keep it consistent with `agents.md`.

---

You are the lead engineer and design-system implementer for Promptolog («Промптолог»): a Bitrix24 web app on the Alaio Vibecode platform that turns raw ideas into structured prompts for Claude, ChatGPT, Kimi, Qwen and Grok. The owner works in GitHub Codespaces and shares the repo as `repomix-output.xml`.

## Language
- Think, write code, comments, commits, docs and search queries in English.
- Reply to the owner in Russian (status, explanations, final report). App UI strings are Russian and live only in `apps/web/src/strings.ru.ts`.

## Sources of truth, in priority order
1. The owner's current message.
2. `agents.md` (operating manual), `design.md` (UI spec «Ноябрь» plus Addendum A), `HANDOFF.md` (architecture, decisions, open risks), `OPERATIONS.md`.
3. The repomix snapshot. It is read-only and may be stale. If a file you need is missing, say so and ask for it; never guess its contents.
If sources conflict, say so in one line and follow the higher one.

## Deliverables
- Default output: ONE idempotent Python patch script for Codespaces (stdlib only, two-phase validation, `--dry-run` / `--diff` / `--commit`, backups, self-archive to `patches/`) plus the exact Codespaces commands. Follow "Patch-script standard" in `agents.md`.
- Test the script on a clean copy of the repo before delivering whenever the sandbox allows. State plainly what you ran and what you could not.
- Never edit `CHANGELOG.md` or `HANDOFF.md` by hand: use `scripts/docs_update.py`, and never paste its usage placeholders (`...`, `id: summary`).

## Working rules
- Source only: no deployment, no real keys; use `REPLACE_WITH_…` placeholders.
- Preserve business logic, API routes, persisted enums and permissions. UI work does not touch server, shared or tests unless asked.
- Use design tokens only: no one-off colors, spacing, radii or shadows. Read `design.md` before any UI change.
- Do not invent platform API contracts; unverified ones are in `HANDOFF.md` section 10.
- No new dependencies without asking.
- Surface conflicts early (WCAG, iframe/fixed positioning, architecture). Make the smallest maintainable change. Ask at most one blocking question; otherwise state assumptions and proceed.

## Style
- No narration of your process, no long preambles.
- Final report in Russian, short: what changed, files, how verified, deviations and risks, commands to run.
- Deliver the patch as a downloadable file when file tools are available, otherwise as one code block, with commands in a separate short block.
''',
}

CHANGELOG_ENTRIES = {
    "Added": [
        "`design.md`: canonical «Ноябрь» design system (owner's AI-first brief v1.0, formatting normalised, wording unchanged) plus Addendum A: mapping to Promptologist screens, WCAG contrast audit with proposed token overrides, iframe/composer conflict, open decisions D1-D5, implementation map. The UI redesign itself is not implemented yet.",
        "`agents.md`: operating manual for AI agents (language policy, hard rules, patch-script standard, Codespaces commands, UI QA, report format) and `CLAUDE.md` that imports it for Claude Code.",
        "`docs/claude-project-instructions.md`: custom instructions text for the Claude Project.",
    ],
    "Changed": [
        "README.md: project documents section; the Design bullet points to the target design system.",
        "`repomix.config.json`: patch scripts in the repo root (`patch_*.py`) are excluded from packs.",
    ],
    "Fixed": [
        "Removed placeholder entries (`...`, `id: summary`) that were written into CHANGELOG.md and HANDOFF.md by running the docs tool usage examples verbatim.",
    ],
}
HANDOFF_SUBS = [
    (
        "patches/                            applied patch scripts (see section 16)",
        "patches/                            applied patch scripts (see section 16)\n"
        "design.md                           canonical UI spec: «Ноябрь» brief v1.0 + Addendum A (mapping, contrast overrides, decisions D1-D5)\n"
        "agents.md, CLAUDE.md                operating manual for AI agents; CLAUDE.md imports agents.md for Claude Code\n"
        "docs/claude-project-instructions.md text pasted into the Claude Project custom instructions",
    ),
]
HANDOFF_DECISIONS = [
    "Canonical UI is the «Ноябрь» design system (Minimal Editorial Workspace: light canvas, warm neutrals, one terracotta accent, floating composer). It supersedes the v1.0 neo-glassmorphism and is specified in `design.md`: Part I is the owner's brief v1.0 (formatting normalised, wording unchanged), Addendum A maps it onto this codebase and holds the overrides. The redesign is not implemented yet; the code still ships the glassmorphism UI.",
    "Brief concepts without a counterpart in this app are not invented: the eight-stage stepper has no real data source (agent run steps are not exposed by any API; generation progress is three transient client states) and the composer has no attachment or voice controls. The `Stepper` is built only if the owner assigns a data source (design.md A5, decision D3).",
    "The contrast audit of the Brief tokens against WCAG 2.2 AA produced proposed overrides (design.md A4): secondary and muted text, accent fill with white text, success and warning text, control borders, Grok identity dot. Brief hex values stay in Part I as the reference; implementation uses the overrides once the owner confirms (D5).",
    "`agents.md` is the operating manual for AI agents; `CLAUDE.md` imports it for Claude Code; `docs/claude-project-instructions.md` is the text pasted into the Claude Project custom instructions. Keep the three consistent.",
]
HANDOFF_LIMITATIONS = [
    "Floating composer vs the Bitrix24 iframe auto-height (`vibe:resize`): `position: fixed` and `100vh` anchor to the full-height frame, not to the visible window, so the Brief's fixed composer cannot be built correctly until the placement iframe height behavior is confirmed (design.md A6, conflict C1, decision D4).",
]
HANDOFF_PATCHES = [PATCH_ID + ": design.md (Ноябрь + Addendum A), agents.md, CLAUDE.md, Claude project instructions, docs placeholder cleanup"]

README_DESIGN_OLD = "- **Design**: neo-glassmorphism, dark/light/system themes, accessible, reduced-motion aware."
README_DESIGN_NEW = (
    "- **Design**: neo-glassmorphism, dark/light/system themes, accessible, reduced-motion aware. "
    "The target design system («Ноябрь», light editorial workspace) is specified in `design.md` and is not implemented yet."
)
README_DOCS_ANCHOR = "## Environment variables (names only; see `.env.example`)"
README_DOCS_BLOCK = """## Project documents
| File | Purpose |
|---|---|
| `agents.md` | Operating manual for AI agents: language policy, hard rules, patch-script standard, QA, report format. `CLAUDE.md` imports it for Claude Code. |
| `design.md` | Canonical UI specification («Ноябрь» brief v1.0 plus Addendum A for this app). Mandatory reading for UI work. |
| `HANDOFF.md` | Architecture, API, data model, decisions, open risks (maintained by `scripts/docs_update.py`). |
| `OPERATIONS.md` | Deploy, verify, rotate, roll back. |
| `CHANGELOG.md` | Release history (maintained by `scripts/docs_update.py`). |
| `docs/claude-project-instructions.md` | Text for the Claude Project custom instructions. |

"""
REPOMIX_OLD = '"customPatterns": ["deliverables/**", "patches/**", "*.zip"]'
REPOMIX_NEW = '"customPatterns": ["deliverables/**", "patches/**", "*.zip", "patch_*.py"]'


class Plan:
    def __init__(self, root: pathlib.Path):
        self.root, self.files, self.errors, self.notes = root, {}, [], []

    def disk(self, rel: str):
        p = self.root / rel
        return p.read_text(encoding="utf-8") if p.is_file() else None

    def read(self, rel: str):
        return self.files[rel] if rel in self.files else self.disk(rel)

    def set(self, rel: str, text: str):
        self.files[rel] = text

    def err(self, msg: str):
        self.errors.append(msg)

    def replace_once(self, rel: str, old: str, new: str, marker: str | None = None):
        t = self.read(rel)
        if t is None:
            return self.err(f"{rel}: file not found")
        if (marker or new) in t:
            return
        n = t.count(old)
        if n != 1:
            return self.err(f"{rel}: anchor found {n}x (expected 1): {old[:70]!r}")
        self.set(rel, t.replace(old, new, 1))


def find_root(start: pathlib.Path) -> pathlib.Path:
    for d in [start, *start.parents]:
        pj = d / "package.json"
        if pj.is_file():
            try:
                if json.loads(pj.read_text(encoding="utf-8")).get("name") == "promptolog":
                    return d
            except ValueError:
                pass
    raise SystemExit("error: run this from inside the promptolog repo (package.json with name 'promptolog' not found)")


def load_docs_tool(root: pathlib.Path):
    path = root / "scripts" / "docs_update.py"
    if not path.is_file():
        raise SystemExit("error: scripts/docs_update.py not found; apply patch_2026-11-20_agent-graph-and-hygiene.py first")
    spec = importlib.util.spec_from_file_location("docs_update", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def strip_placeholders(plan: Plan):
    """Remove lines written by running the docs tool usage examples verbatim."""
    cl = plan.read("CHANGELOG.md")
    if cl is not None and re.search(r"(?m)^- \.\.\.$", cl):
        out = re.sub(r"(?m)^- \.\.\.\n", "", cl)
        out = re.sub(r"(?m)^### [^\n]+\n(?:[ \t]*\n)*(?=^### |^## |\Z)", "", out)
        out = re.sub(r"\n{3,}", "\n\n", out).rstrip("\n") + "\n"
        plan.set("CHANGELOG.md", out)
        plan.notes.append("CHANGELOG.md: removed placeholder '- ...' entries")
    ho = plan.read("HANDOFF.md")
    if ho is not None:
        out = re.sub(r"(?m)^\d+\. \.\.\.\n", "", ho)
        out = re.sub(r"(?m)^- \d{4}-\d{2}-\d{2} id: summary\n", "", out)
        if out != ho:
            plan.set("HANDOFF.md", out)
            plan.notes.append("HANDOFF.md: removed placeholder numbered items and the 'id: summary' patch-log line")


def build_plan(root: pathlib.Path, force_docs: bool) -> Plan:
    plan = Plan(root)
    du = load_docs_tool(root)

    # 1) new documents (never overwrite differing content unless forced)
    for rel, content in NEW_FILES.items():
        cur = plan.disk(rel)
        if cur is None or (force_docs and cur != content):
            plan.set(rel, content)
        elif cur != content:
            plan.notes.append(f"SKIPPED {rel}: exists with different content (use --force-docs to overwrite)")

    # 2) README and repomix config
    plan.replace_once("README.md", README_DESIGN_OLD, README_DESIGN_NEW)
    plan.replace_once("README.md", README_DOCS_ANCHOR, README_DOCS_BLOCK + README_DOCS_ANCHOR, marker="## Project documents")
    plan.replace_once("repomix.config.json", REPOMIX_OLD, REPOMIX_NEW, marker='"patch_*.py"')
    rc = plan.read("repomix.config.json")
    if rc is not None:
        try:
            json.loads(rc)
        except ValueError as e:
            plan.err(f"repomix.config.json would be invalid JSON: {e}")

    # 3) placeholder cleanup, then 4) scripted docs
    strip_placeholders(plan)
    cl = plan.read("CHANGELOG.md")
    if cl is None:
        plan.err("CHANGELOG.md: file not found")
    else:
        plan.set("CHANGELOG.md", du.changelog_add(cl, CHANGELOG_ENTRIES, "Unreleased", PATCH_DATE))
    ho = plan.read("HANDOFF.md")
    if ho is None:
        plan.err("HANDOFF.md: file not found")
    else:
        try:
            plan.set("HANDOFF.md", du.handoff_apply(ho, PATCH_DATE, HANDOFF_DECISIONS, HANDOFF_LIMITATIONS, HANDOFF_PATCHES, HANDOFF_SUBS))
        except SystemExit as e:
            plan.err(f"HANDOFF.md: {e}")
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="validate and list changes, write nothing")
    ap.add_argument("--diff", action="store_true", help="with --dry-run: print unified diffs of existing files")
    ap.add_argument("--commit", action="store_true", help="git add -A && git commit after applying")
    ap.add_argument("--no-backup", action="store_true", help="skip .patch-backup/ copies")
    ap.add_argument("--force-docs", action="store_true", help="overwrite design.md, agents.md, CLAUDE.md, docs/claude-project-instructions.md if they differ")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()

    root = find_root(pathlib.Path(a.root).resolve() if a.root else pathlib.Path.cwd())
    plan = build_plan(root, a.force_docs)
    if plan.errors:
        print("PATCH ABORTED, nothing written:")
        for e in plan.errors:
            print("  -", e)
        return 1
    for n in plan.notes:
        print("note:", n)

    changes = [(rel, plan.disk(rel), new) for rel, new in sorted(plan.files.items()) if plan.disk(rel) != new]
    if not changes:
        print("Nothing to do: patch already applied.")
        return 0
    for rel, old, new in changes:
        print(f"{'create' if old is None else 'update'}  {rel}")
        if a.dry_run and a.diff and old is not None:
            sys.stdout.writelines(list(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}"))[:80])
    if a.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    if not a.no_backup:
        for rel, old, _ in changes:
            if old is not None:
                dst = root / ".patch-backup" / PATCH_ID / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / rel, dst)
    for rel, _, new in changes:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new, encoding="utf-8", newline="\n")
    me = pathlib.Path(__file__).resolve()
    archive = root / "patches" / me.name
    if me != archive and not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(me, archive)
        print(f"archive  patches/{me.name}")
    print(f"\nApplied {len(changes)} file change(s). Next: npm ci && npm run build && npm test")

    if a.commit:
        try:
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "docs: add design.md (Ноябрь), agents.md, Claude project instructions"], cwd=root, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("git commit failed:", e)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
