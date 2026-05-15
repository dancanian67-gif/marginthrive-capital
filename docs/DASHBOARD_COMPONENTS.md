# Dashboard component naming & usage map

Lightweight guidelines for reusing the existing `dashboard-*` classes when adding tabs and panels. **No redesign required**—compose with these wrappers and extend only when a pattern diverges.

## Core layout (every tab)

| Class | Use for |
|-------|---------|
| `dashboard-page` | Root wrapper for the whole dashboard view (full-height shell). |
| `dashboard-shell` | Max-width content column; center with `margin: 0 auto`. |
| `dashboard-content` | Vertical padding for the main column (`padding` on the shell’s main area). |
| `dashboard-section` | One logical block per screen region (spacing between stacked sections). |
| `dashboard-section-header` | Title row above a section (`margin-bottom` only; no bespoke margins on `h*` inside). |
| `dashboard-title` | Primary heading for that section (keeps alignment/typography consistent). |

**Pattern:** Tab body → `dashboard-page` → `main.dashboard-shell.dashboard-content` → one or more `dashboard-section`s.

## Surfaces: cards vs glass vs analytics/table shells

| Class | Use for |
|-------|---------|
| `dashboard-glass` | Frosted panel: charts, KPI strips, dense tables—any “panel” on the dark canvas. Compose with card/table helpers below. |
| `dashboard-card` | Inner padding + radius on a panel; pair with `dashboard-glass`. |
| `dashboard-table-container` | Horizontal scroll + padding context for wide tables (`overflow-x: auto`). |
| `dashboard-analytics-container` | Chart or metrics block with a consistent minimum height; use inside `dashboard-glass` when the block is chart-like. |

**Compose examples (conceptual):**

- **KPI row / small stat cards:** `dashboard-glass dashboard-card` (no table container).
- **Data table:** `dashboard-glass dashboard-card dashboard-table-container` + inner `table.dashboard-table`.
- **Chart / analytics block:** `dashboard-glass dashboard-card dashboard-analytics-container` (place chart markup inside).

## Tables

| Class | Use for |
|-------|---------|
| `dashboard-table` | All tabular data in the dashboard. Use `th` / `td` only; avoid `border` / `style` on `table`. |

## Analytics utility shells (CSS-only)

Lightweight layout/visual primitives for analytics-heavy tabs. Compose with existing `dashboard-glass` + `dashboard-card` where you need the outer frosted panel.

| Class | Use for |
|-------|---------|
| `dashboard-kpi-grid` | Responsive grid for KPI / stat tiles. Direct children should be `dashboard-glass dashboard-card` (or similar) mini-panels. |
| `dashboard-chart-frame` | Inner “plot area” inside an analytics card: drop a chart library root element or canvas inside; use within `dashboard-analytics-container` for consistent height. |
| `dashboard-insight-panel` | Narrative / summary callout (headline + short copy, bullets optional). Left-accent bar matches the premium accent system. |

**Typical compositions:**

- **KPI strip:** `div.dashboard-kpi-grid` → N × `div.dashboard-glass.dashboard-card` (each holds label + value).
- **Chart block:** `div.dashboard-glass.dashboard-card.dashboard-analytics-container` → `div.dashboard-chart-frame` → chart markup.
- **Insight below chart:** Sibling `div.dashboard-insight-panel` in the same `dashboard-section`, or nested inside the card after the chart frame.

## Tab-specific guidance

### Overview

- One `dashboard-section` for page title (“Overview”).
- Optional second `dashboard-section` for KPIs: wrap tiles in `dashboard-kpi-grid`; each tile remains `dashboard-glass dashboard-card`.
- Deeper summaries: reuse `dashboard-analytics-container` inside glass for charts.

### Applications

- Section header + single `dashboard-glass dashboard-card dashboard-table-container` wrapping `table.dashboard-table`.
- Filters/actions: keep in `dashboard-section-header` or a slim `dashboard-glass dashboard-card` row above the table—do not bypass `dashboard-section` spacing.

### Analytics

- Each chart or metric group = one `dashboard-section` (optional subheading in header).
- Body: `dashboard-glass dashboard-card dashboard-analytics-container` → inner `dashboard-chart-frame` for the plot; optional `dashboard-insight-panel` for interpretation copy.

### Settings

- Group related fields in `dashboard-section`s; each group is one `dashboard-glass dashboard-card` (form layout inside—no new global form selectors if avoidable).
- Long settings pages: stack sections; don’t merge unrelated groups in one card.

### Activity panels

- Treat as a **panel**, not a full table: `dashboard-glass dashboard-card` with a list/timeline inside.
- If the list is wide or has many columns, wrap in `dashboard-table-container` and use `dashboard-table` only when it’s true tabular data.

### Analytics sections (multi-block pages)

- Order: high-level KPI strip (`dashboard-glass dashboard-card`) → then one `dashboard-section` per chart (`dashboard-analytics-container`).
- Keep section titles in `dashboard-section-header` + `dashboard-title` (or a smaller heading class later—still under the same header wrapper).

## Naming discipline

- **Prefix:** All dashboard-specific layout/surface classes stay under `dashboard-*`.
- **Composition:** Prefer `dashboard-glass` + `dashboard-card` + optional `dashboard-table-container` or `dashboard-analytics-container` over new one-off class names.
- **Avoid:** Inline `style=""` on dashboard markup; new global `table` rules—scope under `.dashboard-table` or `.dashboard-page` if something is truly global later.

## Quick reference

```
dashboard-page
  └── dashboard-shell.dashboard-content
        └── dashboard-section
              ├── dashboard-section-header
              │     └── dashboard-title
              └── dashboard-glass.dashboard-card[.dashboard-table-container|.dashboard-analytics-container]
                    ├── dashboard-kpi-grid → (tiles)
                    ├── dashboard-chart-frame → (chart root)
                    ├── dashboard-insight-panel → (copy)
                    └── table.dashboard-table | list content
```

This map is documentation only; it does not change runtime behavior or backend logic.
