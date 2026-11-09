# Phase 7: Frontend & Full Local Site - Context

**Gathered:** 2026-11-09 (discussion with owner in the Phase 6 session)
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the Phase 5 minimal page with the full local site: Energy (overview), Weather, Performance and About pages, styled after the owner's reference video, running against the local FastAPI backend that serves the deployed TFT registry. Small backend additions only where the pages need data the API does not expose yet. No model changes, no retraining, no re-run of `evaluate --final`.

Requirements: UI-01..UI-09 (ROADMAP Phase 7 success criteria 1-5).

</domain>

<decisions>
## Implementation Decisions

### Visual reference (owner, 2026-11-09)
- **D-31:** Reference = owner's video `Arastoo___A_clean_and_premium_admin_dashboard_UI...(720p)~2.mp4` in the repo root (sharper copy of `WhatsApp Video 2026-11-09 at 11.31.27 PM.mp4`, 5.6 s, 720x1280 phone recording of a desktop "Admin Dashboard V2"). Owner wants the same look and feel ("that exact glossy finish").
  - Ocean/teal-to-blue blurred gradient background, brighter towards the right.
  - Floating rounded glass panels: darker blue glass sidebar, frosted top bar, one large frosted content panel; inside it pale frosted white-blue cards.
  - Left sidebar: logo block, grouped nav sections with small uppercase group labels, outline icons, count badges, active item = bright cyan pill.
  - Header: large bold greeting ("Good afternoon, ...") with a small grey subtitle; dark navy pill primary button plus a light secondary pill button on the right.
  - Cards: icon chip top-left, big bold number, small label, tiny grey sub-label, optional small coloured "+x%" badge top-right.
  - Charts: light sky-blue bars with the latest bar bright cyan and a value label; a segmented pill toggle (dark selected segment); donut with multi-colour segments and centre value; ring progress with centre %.
  - Motion: on page change the content panel blurs to an empty frosted state, then cards fade/slide in staggered, numbers count up, bars grow left to right, donut/ring fill. Sidebar hover highlight.
  - Typography: bold geometric sans for headings and numbers; small muted grey for subtitles. Outline icon set (Lucide-like).
- **D-32:** Copy the style, not the template's code, names or images. Drop admin-only elements: search bar, user avatar/name, "Invite an agent", Approve/Review buttons, property photo cards.

### Pages (owner, 2026-11-09)
- **D-33 Energy (first page):** five cards, one per model output (solar kW `t1_kw`, wind kW `t5_kw`, sunlight `ghi`, humidity `rh`, wind speed `ws10`), each with current-hour P50, P10-P90 range and a small trend line; a 72 h chart with a 24h/48h/72h segmented toggle and a target switch (P50 line + P10-P90 band); summary cards (today/tomorrow solar kWh, wind kWh, peak hour, combined energy); a 5x5 correlation grid of the five targets (computed from historical data, static) placed below the chart with one-line explanations of the strong links. Greeting line shows "Davanagere" and a small temperature/condition chip labelled "from Open-Meteo".
- **D-34 Temperature is not a model target.** It must never look like a prediction: only as the small Open-Meteo chip on Energy and on the Weather page.
- **D-35 Weather page:** phone-weather-app style: condition icon (sunny / partly cloudy / cloudy / rain, a simple rule from cloud cover and precipitation), current temperature, hourly strip, 3 day cards with high/low. Cloud cover, rain and temperature come from Open-Meteo, labelled as such; humidity, sunlight and wind speed shown there are our model's forecasts and labelled as ours.
- **D-36 Performance page:** TFT vs baseline 3 skill per target, error by horizon, P10-P90 coverage with wind flagged as less reliable (coverage 0.66 ws10 / 0.68 t5_kw vs 0.80 nominal, D-30 limitation reported, not fixed), leaderboard, skill heatmap, validation scatters (roadmap criterion 4).
- **D-37 About page:** project, site and plant specs, methodology, simulated-energy caveat, wind capacity-factor story, attribution NASA POWER, Open-Meteo (CC BY 4.0), Kaggle. Footer: git SHA, data-through date, model version.

### Theme and layout
- **D-38:** Default theme = the light glossy blue of the video. A Settings menu (gear icon in the top bar) holds a light/dark toggle; choice remembered in localStorage (wrapped in try/catch).
- **D-39:** Charts sit on more solid cards than the background glass so thin lines and bands stay readable.
- **D-40:** Phone (375 px): sidebar becomes a bottom navigation bar. All times IST, with "last updated" and the stale warning (roadmap criterion 2).
- **D-41:** Keep roadmap criteria: synchronized hover across the five target panels where five panels are shown, "simulated energy" label on t1_kw and t5_kw, model badge per target linking to Performance.

### Stack
- **D-42:** React 19 + Vite 8 + TypeScript + Tailwind 4 (Vite plugin) + Recharts 3 + `motion` (formerly Framer Motion; import from `motion/react`) + lucide-react icons. @tanstack/react-query for fetch/polling, react-router-dom for page URLs (STACK.md).
- **D-43:** Backend additions allowed: a weather endpoint (hourly temperature, cloud cover, precipitation from the cached live Open-Meteo fetch), a correlation endpoint or static JSON, performance data (prob metrics, heatmap, wind CF) and a footer/build-info endpoint (git SHA, data-through, model from `models/deployed/registry.json`). Keep `swf.api` free of torch/darts imports.

### Claude's Discretion
- Exact component split, colour tokens, font choice (free close match), spacing, chart details.
- Skills to use (owner request): design-taste-frontend (dashboard mode), impeccable, ui-ux-pro-max (design-system), dataviz, apple-design for mobile, find-docs/context7 for Motion/Recharts/Tailwind 4 docs, Playwright side-by-side screenshots against the video, design-critique + accessibility-review at the end. Ask the owner before installing any new skill.

</decisions>

<canonical_refs>
## Canonical References

- `docs/PRD.md` (UI sections), `.planning/REQUIREMENTS.md` UI-01..UI-09, `.planning/ROADMAP.md` Phase 7
- `.planning/research/STACK.md` frontend table (versions)
- `src/swf/api/main.py`, `src/swf/api/schemas.py` (current endpoints: /api/health, /api/forecast, /api/forecast/summary, /api/history, /api/metrics, /api/site)
- `models/deployed/registry.json`, `reports/evaluation/*.csv|png`
- Reference video in the repo root (D-31)

</canonical_refs>

<code_context>
## Existing Code Insights

- `frontend/` is the Phase 5 minimal page (App.tsx ~96 lines, index.css), only react/react-dom installed.
- `python -m swf serve` serves the API and the built `frontend/dist` (static mount last).
- Live check 2026-11-09: refresh with the deployed TFT registry works, `/api/forecast` 0.02 s, 72 h x 5 targets with p10/p50/p90.

</code_context>

<deferred>
## Deferred Ideas

- Cloud deployment and cold-start "waking up" state (v2).
- Wind band recalibration (owner chose to report the limitation instead).

</deferred>

---

*Phase: 07-frontend-full-local-site*
