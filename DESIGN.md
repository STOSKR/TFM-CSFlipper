<!-- SEED - re-run $impeccable document once there's code to capture the actual tokens and components. -->
---
name: CSFlipper
description: Operational dashboard for CS2 market simulation, supervised signals, and MARL agents.
---

# Design System: CSFlipper

## 1. Overview

**Creative North Star: "The Trading Desk Ledger"**

CSFlipper should feel like a quiet trading desk built for a technical operator: precise, legible and grounded in real state. The interface is a product surface, not a marketing site. It should help the user inspect data, understand decisions and track progress without fighting visual noise.

The system uses moderate density: tables, compact metrics, tabs and status panels are welcome when they serve comparison. The screen should never feel sparse for decoration, but it also must not feel visually complicated. Each section gets one job and one clear hierarchy.

It explicitly rejects SaaS landing-page cliches, generic AI dashboards, purple gradient decoration, glassy panels, fake hero metrics and repeated card grids with no operational value.

**Key Characteristics:**

- Calm operational structure.
- Moderate information density.
- Explicit model and agent state.
- Clear status language.
- Low ornament, high traceability.

## 2. Colors

The palette should be restrained: tinted neutrals, one primary accent and semantic states for risk and progress. Exact color tokens will be resolved during implementation.

### Primary

- **Signal Blue** ([to be resolved during implementation]): used for primary actions, active navigation and selected filters. It should feel precise rather than electric.

### Secondary

- **Ledger Green** ([to be resolved during implementation]): used only for positive realized outcomes, available capital and successful checks.

### Tertiary

- **Risk Amber** ([to be resolved during implementation]): used for warnings, experimental model notices, blocked capital and review states.

### Neutral

- **Workbench Surface** ([to be resolved during implementation]): the main background, slightly tinted rather than pure white.
- **Panel Surface** ([to be resolved during implementation]): raised or grouped areas for tables, controls and state panels.
- **Ink Text** ([to be resolved during implementation]): primary text with strong contrast but no pure black.
- **Quiet Border** ([to be resolved during implementation]): dividers, table rules and control boundaries.

### Named Rules

**The Accent Ration Rule.** Primary accent is for action and selection only. It must not become decoration.

**The State Honesty Rule.** Success, warning and risk colors always carry text labels. Color alone is forbidden.

## 3. Typography

**Display Font:** Single sans direction, likely system UI or Inter class.
**Body Font:** Same sans family.
**Label/Mono Font:** Tabular or mono style only for IDs, timestamps, numeric traces and code-like values.

**Character:** Typography should feel like a mature tool: compact, calm and precise. No display fonts in labels, buttons or data tables.

### Hierarchy

- **Display** (600, restrained size, tight line-height): only for top-level app title or empty-state headline.
- **Headline** (600, medium size, compact line-height): page and major panel headings.
- **Title** (600, small-medium size): section titles, table group names and cards with a real decision role.
- **Body** (400, normal size, 1.45 to 1.6 line-height): explanations, model limitations and state details.
- **Label** (500 to 600, small size, normal letter spacing): form labels, table headers, status labels and metadata.

### Named Rules

**The Data First Rule.** Numeric values and states must be easier to scan than decorative headings.

## 4. Elevation

Depth should come mostly from tonal layering, borders and spacing. Shadows are allowed only for overlays, menus or focused floating elements. Static dashboard panels should not look like floating marketing cards.

### Named Rules

**The Flat By Default Rule.** Surfaces are grouped by tone and border first. Shadows are reserved for interaction layers.

## 5. Components

### Buttons

- **Shape:** Slightly curved and compact (target 6px to 8px radius).
- **Primary:** One accent background, high contrast text, used for clear commands only.
- **Hover / Focus:** Subtle tone shift and visible focus ring.
- **Secondary / Ghost:** For toolbar actions, filters and non-destructive operations.

### Chips

- **Style:** Small, text-first status tags with restrained background tints.
- **State:** Selected chips are visibly active through background and border, not saturation alone.

### Cards / Containers

- **Corner Style:** Small radius, never pill-like.
- **Background:** Tonal surfaces that separate work areas.
- **Shadow Strategy:** Flat by default.
- **Border:** Quiet borders for tables, panels and grouped controls.
- **Internal Padding:** Compact but breathable, with denser spacing in tables.

### Inputs / Fields

- **Style:** Clear border, neutral surface and visible labels.
- **Focus:** Strong accessible focus ring.
- **Error / Disabled:** Text label plus semantic tone.

### Navigation

Top-level navigation should be predictable: app sections such as Progreso, Modelo, Simulacion, Agentes and Recomendaciones. Active state should be clear and restrained. Mobile layout should collapse to tabs or a compact menu, not hide core status.

## 6. Do's and Don'ts

### Do:

- **Do** design the first screen as the actual tool, not a landing page.
- **Do** use moderate density with tables, filters, timelines and compact status panels.
- **Do** show model version, threshold and limitations near predictions.
- **Do** keep agent state legible: status, observation, action, reason and reward should be adjacent.
- **Do** reserve visual emphasis for decisions, warnings and active selections.

### Don't:

- **Don't** use SaaS landing-page cliches, hero sections or decorative value props.
- **Don't** use purple gradients, glassmorphism, bokeh, decorative orbs or generic AI-dashboard styling.
- **Don't** create repeated identical card grids when a table, timeline or segmented control would be clearer.
- **Don't** make the interface visually complicated with too many colors, nested panels or ornamental motion.
- **Don't** present experimental model output as an automatic purchase decision.
