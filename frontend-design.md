# TrustRail Frontend Design System & Implementation Guide

> **Purpose:** This document is the canonical design and frontend implementation reference for TrustRail. Every AI coding assistant, developer, and future UI component should follow it before creating or changing frontend code.
>
> **Product statement:** TrustRail is an authorization and transaction-control layer that lets AI agents act on real systems while keeping every action policy-checked, human-approved, auditable, and recoverable.
>
> **Design principle:** Make trust visible. The interface must show what the agent proposed, what the deterministic engine decided, what a human approved, what was executed, and what evidence proves the outcome.

**Status:** Frontend design specification  
**Backend source of truth:** The current Python implementation and its FastAPI OpenAPI schema  
**Frontend target:** React + Vite + TypeScript  
**Backend target:** Python 3.12+, FastAPI, Pydantic, SQLite, Otari integration, GitHub MCP  
**Primary demo environment:** GitHub sandbox repository through the hosted Otari gateway

---

## 1. Product and design intent

### 1.1 What TrustRail is

TrustRail is not a chatbot, a generic AI assistant, or a conventional task-management dashboard. It is a **control plane for agentic actions**.

The user should understand these boundaries without reading documentation:

1. **Agent / planner:** proposes actions and can use only its restricted model-facing tools.
2. **Ground-truth resolver:** obtains authoritative issue facts from GitHub through read-only MCP calls.
3. **Deterministic authorization engine:** evaluates the active policy against validated facts. The LLM is never the authority.
4. **Human approval gate:** requires a person to approve or reject eligible proposed writes.
5. **Transaction executor:** performs prechecks, claims dispatch, and makes a single write attempt.
6. **Reconciler:** investigates uncertain outcomes using read-only evidence rather than blindly retrying.
7. **Audit ledger:** records the sequence of events in an append-only, hash-chained record.

The UI must reinforce these responsibilities. Never visually imply that the model itself approves, authorizes, or directly executes a write.

### 1.2 The product's central story

The main experience should guide a judge through this sequence:

`Policy → Dry run → Agent run → Proposals → Deterministic decisions → Human approval → Dispatch → Outcome / Reconciliation → Ledger evidence`

The most important visual moment is the lost-response scenario:

- A non-idempotent GitHub action is applied.
- The response is lost.
- TrustRail records `INDETERMINATE`.
- TrustRail does not blindly retry.
- A read-only probe checks GitHub for the transaction marker and issue state.
- The UI shows the evidence and the reconciled result.
- The ledger preserves the sequence.

The interface must make `INDETERMINATE` look like an explicit, controlled uncertainty state—not like success, failure, or a generic loading spinner.

### 1.3 Desired product personality

- Serious, precise, technical, calm, and trustworthy.
- Modern developer infrastructure / security operations console.
- Dense enough for engineers, but legible to a judge seeing it for the first time.
- Evidence-first, not decoration-first.
- Clear hierarchy, compact data tables, restrained motion, and useful empty states.
- No generic AI gradients, cartoon robots, glowing brains, random stock photography, or excessive glassmorphism.

### 1.4 Design references in spirit

Use the visual discipline of high-quality developer tools and infrastructure consoles: clear navigation, strong typography, compact tables, precise status indicators, readable event timelines, and meaningful system feedback.

Do not copy another product's branding, layout pixel-for-pixel, or logo. TrustRail must have its own identity.

---

## 2. Brand identity

### 2.1 Name and spelling

The product name is **TrustRail** (one word, capital T and R). Use this spelling consistently in the UI, page titles, metadata, and documentation.

The name suggests a guarded execution rail: actions move along a controlled path, and policy / approval / evidence checks act as the rails.

### 2.2 Logo concept

Create a small, original, geometric vector mark. Preferred concept:

- Two parallel vertical rails or paths.
- A short horizontal bridge / checkpoint between them.
- A small check mark or shield-like negative-space shape at the checkpoint.
- Simple enough to remain recognizable at 16–24 px.
- Use the same mark in the sidebar, browser favicon, loading shell, and README.

The mark should communicate **controlled passage**, not a generic padlock. Keep the wordmark as `TrustRail` in a clean sans-serif font.

Deliver the mark as an inline SVG or local SVG asset. Do not depend on a remote image host.

### 2.3 Logo and partner marks

- TrustRail logo: primary product identity; use the original local SVG.
- GitHub: use a recognizable GitHub mark only beside the connected repository / integration label. Do not make GitHub the product logo.
- Otari: use its official mark only if a valid official asset is available in the project. Otherwise render the text `Otari` in the integration / gateway panel.
- Mozilla Devs Wilding: optional hackathon attribution in an About / footer area. It must not compete with TrustRail's own identity.
- Never invent partner logos or use low-quality screenshots as logos.

---

## 3. Visual system

### 3.1 Theme

Use a **dark-first interface**. The main dashboard should feel like a professional security console, not a black landing page.

Use near-black navy surfaces, cool slate borders, off-white primary text, muted blue-gray secondary text, and a restrained cyan accent. Status colors must be semantic and consistent.

Suggested design tokens (CSS custom properties):

```css
:root {
  color-scheme: dark;

  --tr-bg: #0B1120;
  --tr-bg-elevated: #0F172A;
  --tr-surface: #111C2F;
  --tr-surface-raised: #17243A;
  --tr-surface-hover: #1C2B43;

  --tr-border: #26364D;
  --tr-border-strong: #344963;

  --tr-text: #E6EDF7;
  --tr-text-secondary: #A7B5C8;
  --tr-text-muted: #718198;

  --tr-accent: #38BDF8;
  --tr-accent-hover: #7DD3FC;
  --tr-accent-subtle: rgba(56, 189, 248, 0.12);

  --tr-success: #34D399;
  --tr-success-subtle: rgba(52, 211, 153, 0.12);

  --tr-warning: #FBBF24;
  --tr-warning-subtle: rgba(251, 191, 36, 0.12);

  --tr-danger: #F87171;
  --tr-danger-subtle: rgba(248, 113, 113, 0.12);

  --tr-purple: #A78BFA;
  --tr-purple-subtle: rgba(167, 139, 250, 0.13);

  --tr-info: #60A5FA;
  --tr-info-subtle: rgba(96, 165, 250, 0.12);

  --tr-radius-sm: 6px;
  --tr-radius-md: 10px;
  --tr-radius-lg: 14px;

  --tr-shadow-panel: 0 8px 28px rgba(0, 0, 0, 0.20);
}
```

Treat these as the initial palette, not permission to scatter arbitrary hex values through components. If a token needs adjustment, change it centrally and update this document.

### 3.2 Semantic status colors

Use status color only for status, decisions, or meaningful alerts. Do not use colored badges as decoration.

| State / decision | Color | Meaning |
|---|---|---|
| `SUCCEEDED` | Green `--tr-success` | Execution or reconciliation has confirmed success |
| `ALLOW` | Green | Policy permits the action without an approval requirement |
| `REQUIRES_APPROVAL` | Amber | Policy conditions passed, but a human decision is required |
| `PENDING_APPROVAL` | Amber | Waiting for a human decision |
| `INDETERMINATE` | Amber / gold | Outcome is unknown; evidence-based reconciliation is required |
| `RECONCILING` | Blue | A read-only probe is gathering evidence |
| `DENY` / `DENIED` | Red | Authorization denied; show the exact reasons |
| `FAILED` | Red | Tool reported a definitive execution error |
| `FAILED_SAFE` | Muted blue-gray | Execution did not start; safe failure classification |
| `REJECTED` | Muted red | Human rejected the proposed action |
| `APPROVAL_INVALIDATED` | Purple | Previously granted approval no longer matches current facts / policy / server configuration |
| `POLICY_INVALID` | Red | Policy is malformed, contradictory, or invalid |
| `NOT_EXECUTED` | Muted blue-gray | Reconciliation evidence indicates the write was not applied; fresh approval is required before a retry |
| `UNRESOLVED` | Orange / amber | Evidence is conflicting or incomplete; human attention is required |
| `DUPLICATE_DETECTED` | Red | More than one transaction marker was found; show an alert |

Important:
- Do not collapse `FAILED`, `FAILED_SAFE`, and `INDETERMINATE` into one “Error” status.
- Do not render `INDETERMINATE` as green or as a completed transaction.
- Do not imply `NOT_EXECUTED` is permission to retry automatically.
- Always pair a color with a text label and, where useful, an icon. Never rely on color alone.
- A state badge should show the exact backend enum, with a human-readable tooltip or description.

### 3.3 Typography

Use a clean UI sans-serif for normal interface text and a monospace face for IDs, hashes, JSON, request IDs, timestamps where precision matters, and code.

Preferred stack:

```css
--tr-font-sans: Inter, ui-sans-serif, system-ui, -apple-system,
                BlinkMacSystemFont, "Segoe UI", sans-serif;
--tr-font-mono: "JetBrains Mono", "SFMono-Regular", Consolas,
                "Liberation Mono", monospace;
```

If a local font cannot be bundled quickly, use the system stack. Do not block implementation on font downloads.

Typography scale:
- Page title: 24–28 px, semibold.
- Section title: 16–18 px, semibold.
- Card title: 13–15 px, medium / semibold.
- Body: 13–14 px.
- Table: 12–13 px, with comfortable line height.
- Helper text / metadata: 11–12 px.
- IDs / hashes: 11–12 px monospace.

Use sentence case for headings. Avoid oversized marketing typography inside the application.

### 3.4 Spacing and layout

Use a 4 px base spacing scale. Typical values:
- 4 px: icon-to-label gap.
- 8 px: compact internal spacing.
- 12 px: control / table cell spacing.
- 16 px: card padding and form groups.
- 20–24 px: section separation.
- 28–32 px: page section separation.

The dashboard should use a consistent 12-column mental grid. Use a maximum content width around 1440 px on wide displays; allow tables to use available width.

### 3.5 Borders, elevation, and surfaces

- Prefer thin borders over heavy shadows.
- Use slightly raised surfaces for cards, menus, and detail panels.
- Keep the background visually distinct from cards.
- Avoid bright borders around every element.
- Use one consistent radius scale; avoid pill-shaped everything.
- Reserve shadows for overlays and floating menus, not every panel.

### 3.6 Icons

Use one consistent outline icon family (Lucide is preferred). Keep icons simple and mostly 14–18 px.

Suggested semantic icons:
- Overview: `layout-dashboard`
- Policy: `shield-check`
- Runs: `workflow`
- Approvals: `user-check`
- Ledger: `scroll-text` or `file-clock`
- Trust Tests: `flask-conical`
- Integrations: `plug`
- Settings: `settings`
- Success: `check-circle-2`
- Denied: `shield-x`
- Pending: `clock-3`
- Indeterminate: `circle-help` or `alert-triangle`
- Reconciliation: `refresh-cw`
- Evidence: `search-check`
- External link: `external-link`

Do not use emoji as interface icons. Emojis may appear only in demo content supplied by GitHub issue text.

---

## 4. Application information architecture

### 4.1 Main navigation

Use a fixed left sidebar on desktop, a compact top bar / drawer on smaller screens, and a clear active navigation state.

Recommended navigation:

1. **Overview**
2. **Policy**
3. **Runs**
4. **Approvals**
5. **Ledger**
6. **Trust Tests**
7. **Integrations** (only if there is meaningful status / configuration data to show)

A separate **Chaos Lab** entry can be included if the fault-injection controls are implemented and available through a supported backend endpoint. Otherwise, keep the controls in the relevant demo / Trust Tests view rather than presenting a non-functional page.

### 4.2 Global application shell

Desktop layout:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Sidebar       │ Top bar: page context | environment | backend status │
│               ├──────────────────────────────────────────────────────┤
│ TrustRail     │                                                      │
│ Overview      │ Main content                                         │
│ Policy        │                                                      │
│ Runs          │                                                      │
│ Approvals     │                                                      │
│ Ledger        │                                                      │
│ Trust Tests   │                                                      │
│               │                                                      │
│               │                                                      │
│               ├──────────────────────────────────────────────────────┤
│ API status    │ Footer: version / demo environment / docs             │
└──────────────────────────────────────────────────────────────────────┘
```

Sidebar:
- Width around 232–248 px expanded; 64–72 px collapsed.
- TrustRail mark + wordmark at the top.
- Navigation labels with icons.
- Optional compact pending-approval count, only when derived from backend data.
- Bottom area: backend connectivity, active repository, and a small environment label.
- Avoid putting sensitive configuration or API keys in the UI.

Top bar:
- Breadcrumb or current page title.
- Current repository / sandbox context, if known from backend configuration.
- Backend health indicator based on `/health`.
- Small environment tag such as `DEMO` or `LOCAL`; do not claim production status unless configured.
- Refresh / last-updated timestamp where polling is used.

### 4.3 Page hierarchy

Every page should follow this order:
1. Page title and one-sentence explanation.
2. Primary action, if any.
3. Most important status / summary.
4. Main table, workflow, or editor.
5. Secondary details and evidence.

Do not make the first screen a wall of cards. Use summary metrics only when they help explain the system state.

---

## 5. Screen specifications

## 5.1 Overview dashboard

**Purpose:** Let a first-time judge understand the current state of TrustRail and jump into the core workflow.

Suggested layout:

- Header: `TrustRail overview` and a short line: `A controlled execution layer for AI agents.`
- Top status strip:
  - Backend health.
  - Active policy status / version, if available.
  - Connected GitHub repository.
  - Otari gateway status, if the backend exposes it.
- Workflow progress / system path:
  `Policy → Agent → Authorization → Approval → Execution → Reconciliation → Ledger`
- Main metrics (only if actual data endpoints exist):
  - Total runs.
  - Transactions awaiting approval.
  - Denied proposals.
  - Indeterminate / unresolved transactions.
  - Successful transactions.
- Recent activity table:
  - Time.
  - Run / transaction.
  - Action.
  - Decision / state.
  - Issue / repository.
  - Open details action.
- Attention panel:
  - Pending approvals.
  - `INDETERMINATE` or `UNRESOLVED` transactions.
  - Invalidated approvals.
  - Ledger verification warning, if a verification result exists.

Do not fabricate metrics or show zero as a default when the backend has not been queried. Use `—` / `Not loaded` until a real response arrives.

Empty state:
- Explain that no runs exist yet.
- Primary CTA: `Create a run` or `Configure a policy`, depending on whether a valid active policy exists.
- Provide a concise explanation of what a run does.

## 5.2 Policy page

**Purpose:** Define what the agent is allowed to propose and what the deterministic engine will permit.

This page should have two clear areas: **Policy input / compilation** and **Validated policy / dry run**.

### Policy compiler panel

- Page title: `Policy`
- Description: `Define the rules TrustRail uses to evaluate proposed actions.`
- Large natural-language policy textarea.
- Example starter text:
  `Only close GitHub issues inactive for at least 30 days and with no P0 or P1 priority label. Require human approval before every close action.`
- Primary button: `Compile policy`
- Show compiler / routing information only if it is safe and actually exposed by backend configuration.
- Loading state should say `Compiling and validating policy…`, not `Authorizing actions…`.

### Ambiguous compiler response

If the compiler returns an `ambiguous` response with questions:
- Show an amber clarification panel.
- Render each question as readable text.
- Do not invent defaults or silently continue.
- Let the user revise the natural-language input and compile again.
- Do not display an invalid or partial policy as active.

### Validated policy result

Show:
- Plain-English summary generated from the validated policy by backend code.
- Policy JSON in a collapsible, syntax-highlighted code panel.
- Schema version.
- Repository.
- Action name and conditions.
- Inactivity threshold.
- Excluded priority labels.
- Approval requirement.
- Maximum actions per run.
- Audit setting.

Important backend boundary:
- Policy compilation produces a validated policy and summary. It does **not** automatically activate the policy, authorize an action, or execute GitHub operations.
- Keep `Compile`, `Dry run`, and `Activate` as separate actions only where the backend supports each action.
- Do not show an `Activate` button unless there is a real activation endpoint and persisted active-policy behavior.
- Do not imply the compiler's LLM output is trusted without strict backend validation.

### Dry-run results

Display the per-issue decisions in a table:

| Column | Content |
|---|---|
| Issue | `#number` and title |
| Priority | P0 / P1 / P2 / P3 / missing |
| Inactive | Number of days |
| Decision | Exact decision enum badge |
| Reasons | Human-readable reason list |
| State | Open / closed |

At the top of the table, show aggregate counts returned by the backend:
- Allowed.
- Requires approval.
- Denied.
- Policy invalid.

Use a compact filter for `All`, `Requires approval`, `Denied`, and `Allowed` only if the response contains these categories.

Dry-run is read-only. The UI must explicitly communicate:
`Dry run only — no approval is created and no GitHub write is performed.`

## 5.3 Runs page

**Purpose:** Start an agent workflow and inspect the proposals it produces.

Header:
- `Runs`
- Description: `Ask the agent to inspect the repository and propose actions. TrustRail evaluates every proposal independently.`

Run creation panel:
- Natural-language request textarea.
- Example:
  `Find stale issues in the configured repository and propose closing the ones that satisfy the active policy.`
- Optional planner model / routing selector only if the current backend request schema explicitly supports a caller-selected value. The current architecture uses server-configured Otari routing policy names; never invent a model selector that the API cannot honor.
- Primary action: `Start run`.

After submission:
- Create a run detail view or open the newly created run.
- Poll the run endpoint while it is active (the build plan specifies polling rather than WebSockets).
- Show the run ID and creation time.
- Show planner progress and termination reason if the backend returns them.
- Show tool-call counts / iteration counts / provider usage only when returned by backend data.
- Distinguish model tool calls from actual GitHub writes.

### Proposals list

Each proposal row / card should show:
- Issue number and title.
- Proposed action: `close_issue`.
- Agent-provided reason.
- Deterministic decision.
- Authorization reasons.
- Current transaction state.
- Link to transaction details.

The agent may propose an action; it does not authorize it. Make that distinction visible.

Decision labels:
- `REQUIRES_APPROVAL`: eligible under policy, awaiting human decision.
- `DENY`: show the deterministic reasons.
- `ALLOW`: show only if the backend actually returns it.
- `POLICY_INVALID`: show the validation / policy error.

Never render a proposal as an approved action merely because the agent proposed it.

## 5.4 Approvals page

**Purpose:** Make human approval explicit, informed, and bound to the exact action and evidence.

This should be one of the most polished pages because it represents the core human-control boundary.

Layout:
- Page title: `Approvals`
- Pending approval count from actual data.
- Filter tabs: `Pending`, `Approved`, `Rejected`, `Invalidated` (only for states available in the API).
- Approval cards or a table with a strong action summary.

Each pending approval must expose, before the user acts:
- Repository and issue.
- Proposed tool / action.
- Exact action arguments (read-only formatted JSON or a concise summary).
- Agent's reason.
- Deterministic authorization decision and reasons.
- Ground-truth facts used by authorization.
- Policy version.
- MCP server revision.
- Binding hash or a shortened fingerprint, if returned.
- Warning that precheck will revalidate facts and server configuration before dispatch.

Actions:
- `Approve` — clear primary action, with a confirmation dialog summarizing the exact action.
- `Reject` — secondary/destructive action, with optional reason only if supported by the API.
- Do not put Approve and Reject adjacent without visual separation.
- Disable both while a request is in flight.
- Prevent duplicate submissions from double clicks.
- After response, refresh the approval / transaction state from the server.

### Approval invalidation

If precheck discovers changed facts, policy, or server configuration:
- Show `APPROVAL_INVALIDATED` in purple.
- Explain the actual reason returned by the backend (for example, `REVISION_CHANGED`, `FACTS_CHANGED`, `POLICY_CHANGED`, `NOW_DENIED`).
- Show old vs current values only when both snapshots are available.
- Explain: `This approval no longer authorizes the current action. Create a new proposal and obtain fresh approval.`
- Never offer a one-click bypass.

## 5.5 Transaction details

This is a key reusable detail view and should be accessible from Runs, Approvals, and Ledger.

Suggested header:
- Transaction ID (copy button).
- State badge.
- Issue / repository.
- Tool name.
- Created / updated timestamps.

Use tabs or sections:
1. **Summary** — action, arguments, decision, current state.
2. **Authorization evidence** — facts snapshot, policy version, server revision, binding hash.
3. **Execution** — dispatch attempt, Otari request IDs, typed outcome classification.
4. **Reconciliation** — probe request, issue closed state, marker count, evidence-based result.
5. **Audit events** — chronological ledger entries.

Use a vertical timeline with:
- Event type.
- Timestamp.
- State transition.
- Relevant reason / payload summary.
- Request ID, where applicable.
- Hash prefix, where applicable.

Do not fabricate missing events or show a continuous timeline if the backend returns only a partial history. Make unavailable evidence explicit.

## 5.6 Ledger page

**Purpose:** Show that TrustRail's audit trail is append-only, linked, and verifiable.

Header:
- `Audit ledger`
- Description: `A chronological, hash-chained record of TrustRail decisions and transaction events.`

Main table:
- Timestamp.
- Event type.
- Transaction ID.
- Run ID, if available.
- State / decision.
- Event sequence.
- Hash prefix.
- Open transaction.

Filters:
- Transaction ID.
- Run ID.
- Event type.
- Date range, only if supported by API.
- State, only if represented in event data.

Ledger verification:
- Button: `Verify ledger`.
- Show an explicit loading state.
- On success, show `Chain verified` with the returned verification details (number of events / transactions only if returned).
- On failure, show `Integrity check failed`, the first reported issue / sequence if available, and a strong warning.
- Do not show a green check merely because the request returned HTTP 200; inspect the actual verification result.
- Never imply that a hash chain proves the truth of external facts. It proves integrity of the recorded chain under the implementation's verification model.

Hash presentation:
- Use monospace.
- Show a shortened prefix in tables.
- Provide a copy control and full hash in the detail view.
- Do not truncate the stored value in the client state.

## 5.7 Trust Tests page

**Purpose:** Demonstrate that the security properties hold under adversarial and failure conditions.

Use a scenario list with one card per supported test. Each card should include:
- Scenario ID and name.
- Short threat description.
- What TrustRail is expected to enforce.
- Run button (only if the scenario runner endpoint exists).
- Latest result: `PASS`, `FAIL`, `NOT RUN`, or `UNAVAILABLE`.
- Evidence / transaction links.
- Timestamp of the latest run.

The build plan identifies these scenario concepts:
- Prompt injection.
- Attribute lie.
- Permission drift.
- State drift.
- Lost response.
- Action limit.
- Crash recovery (if stable / exposed).
- Budget exhaustion (optional and only if the backend reports it reliably).

Do not mark a scenario as passed based on a hardcoded frontend fixture. A `PASS` must come from a backend result with evidence.

### Cross-model comparison

If the backend returns cross-model scenario results, show a comparison table:
- Model / routing option.
- Whether an unauthorized action was proposed.
- Whether TrustRail blocked it.
- Unauthorized writes executed.
- Evidence / run link.

The key message is that model behavior may differ, but deterministic authorization should produce the same policy outcome for the same trusted facts. Do not invent benchmark scores.

## 5.8 Chaos / failure demonstration panel

This is a demo control surface, not a general production setting.

Only show controls that are backed by real, authenticated backend functionality.

Possible controls from the product plan:
- Fault mode selector: `none`, `drop_after_apply`, `delay_after_apply`, `fail_before_apply`, `partial` (only show modes supported by the deployed MCP server).
- Executor mode: safe TrustRail executor vs naive demo-only executor, only if backend supports the selection.
- Reset demo, only if a real reset operation is exposed and authenticated.
- Target issue status.
- Marker count for the current transaction.

Use a visibly separate `Demo controls` panel with a warning:
`Fault injection changes the behavior of the connected sandbox integration. Use only with the demo repository.`

Never expose MCP admin tokens, GitHub PATs, Otari API keys, or backend secrets in frontend code or browser storage.

### Lost-response presentation

When a transaction becomes `INDETERMINATE`, show a dedicated evidence panel:

- State: `INDETERMINATE`
- Explanation: `The write request's outcome could not be confirmed from the response. TrustRail has not blindly retried it.`
- Next action: `Reconcile` only if a real reconciliation action is exposed; otherwise show the backend's current reconciliation status.
- After probe: show issue closed state, transaction marker count, probe request ID, and final evidence classification.
- If one marker and closed: show `SUCCEEDED — reconciled from GitHub evidence`.
- If no marker and open: show `NOT_EXECUTED — a fresh approval is required before retry`.
- If evidence conflicts: show `UNRESOLVED — human investigation required`.
- If marker count exceeds one: show `DUPLICATE_DETECTED` prominently.

Do not use a generic spinning loader to hide uncertainty.

## 5.9 Integrations / system status

If there is time and the backend provides the data, show:
- Backend health.
- Otari gateway reachability / status.
- Configured planner routing name.
- Configured compiler routing name.
- GitHub repository / MCP server identity.
- MCP server revision.
- Last successful read-only check.
- Recent request IDs.

This is a status and observability page, not a credential-management UI. Never display raw secrets. If a value is not exposed by the API, omit it rather than inventing a status.

---

## 6. Core reusable components

Build a small, consistent component library before building each page independently.

### 6.1 App shell
- `AppShell`
- `Sidebar`
- `TopBar`
- `PageHeader`
- `EnvironmentBadge`
- `BackendHealthIndicator`

### 6.2 Status and decision components
- `TransactionStateBadge`
- `AuthorizationDecisionBadge`
- `ScenarioResultBadge`
- `IntegrationStatus`
- `InlineAlert`
- `ApprovalInvalidatedBanner`

Each badge must map known backend enum values to labels, semantic colors, and accessible text. Unknown enum values must render as a neutral `Unknown state: <value>` rather than silently mapping to success.

### 6.3 Data display
- `DataTable`
- `KeyValueGrid`
- `JsonViewer`
- `CopyButton`
- `CodeBlock`
- `Timestamp`
- `HashValue`
- `RequestIdLink`
- `EmptyState`
- `LoadingState`
- `ErrorState`
- `Pagination` (only if needed by the actual API)

### 6.4 Workflow components
- `RunRequestForm`
- `ProposalCard`
- `ApprovalCard`
- `ApprovalConfirmationDialog`
- `TransactionTimeline`
- `ReconciliationEvidencePanel`
- `LedgerVerificationPanel`
- `ScenarioCard`
- `DemoControlsPanel`

### 6.5 Component rules
- Components should be reusable and typed.
- Keep API logic out of presentational components.
- Avoid giant components that own an entire page, all API calls, and all state.
- Prefer explicit props and small view models.
- Avoid unnecessary abstraction for a hackathon-sized application; consistency matters more than building a design-system framework.

---

## 7. Frontend architecture and implementation conventions

### 7.1 Required stack

Follow the project frontend plan unless the repository already contains an established implementation:

- React.
- Vite.
- TypeScript.
- CSS / CSS Modules or a small token-based CSS system.
- Lucide icons (or the icon library already installed).
- A lightweight router if multiple pages are needed.
- One centralized API client.
- Polling for live run / transaction updates; no WebSocket requirement.

Do not introduce a large component framework just to style the application. Prefer CSS and reusable local components. Do not use deprecated styling patterns or add a styling dependency without a concrete need.

### 7.2 Suggested frontend structure

Adapt to the repository's existing frontend structure rather than blindly creating duplicate folders.

```text
web/
  src/
    app/
      App.tsx
      router.tsx
      providers.tsx
    components/
      layout/
      common/
      status/
      data-display/
      workflow/
    features/
      overview/
      policy/
      runs/
      approvals/
      transactions/
      ledger/
      trust-tests/
      integrations/
    lib/
      api/
        client.ts
        errors.ts
        endpoints.ts
      format/
      polling/
    hooks/
    styles/
      tokens.css
      globals.css
      components.css
    types/
      api.ts
      domain.ts
    assets/
      trustrail-mark.svg
```

### 7.3 API integration rules

The backend is the authority. The frontend is a presentation and interaction layer.

- Use the FastAPI API, not direct SQLite access.
- Use one centralized API client with a configurable base URL.
- Use the backend's actual `/api/v1` routes and Pydantic response schemas.
- Inspect the live FastAPI OpenAPI document (`/openapi.json` or `/docs`) before implementing any endpoint not explicitly confirmed in the current backend README.
- Do not invent routes, request fields, response fields, enum values, or query parameters.
- Keep request / response TypeScript types aligned with Pydantic models.
- Prefer generating types from OpenAPI if practical; otherwise maintain typed interfaces and verify them against the schema.
- Handle non-2xx responses using the backend's actual error shape.
- Distinguish network errors, validation errors, authentication errors, conflicts, and server errors.
- Show a useful message to the user; keep raw stack traces out of the UI.
- Never silently convert malformed or missing fields into valid-looking data.
- Never fabricate metrics, transaction states, request IDs, or ledger events.

### 7.4 Confirmed backend integration points from the implementation notes

The following capabilities are documented in the Python backend snapshots:

- FastAPI application with health support.
- Policy compilation through `POST /api/v1/policies/compile`.
- Policy dry-run through `POST /api/v1/policies/dryrun`.
- Agent orchestration with the restricted model-facing tools:
  - `list_issues()`
  - `get_issue(issue_number)`
  - `propose_close(issue_number, reason)`
- Proposal evaluation using independently resolved GitHub facts and the deterministic authorization engine.
- Approval and transaction execution workflows.
- Single-attempt Otari MCP execution without automatic retry.
- Typed outcome classification, including safe failure and uncertain outcomes.
- Startup recovery and reconciliation support.
- Append-only SQLite audit ledger with SHA-256 hash chaining.
- Reconciliation support through a read-only GitHub activity probe.
- Otari routing policies configured on the backend:
  - `trustrail-planner`
  - `trustrail-compiler`

Important: route names and exact request / response schemas for all workflows must be checked against the current backend's OpenAPI schema. Do not copy endpoint paths from the older Go-oriented build plan and assume they are implemented identically in Python.

### 7.5 Security boundaries

- Do not put GitHub PATs, Otari keys, MCP admin tokens, or `TR_ADMIN_TOKEN` in frontend source code.
- Do not hardcode secrets in Vite environment variables prefixed with `VITE_`; those are browser-visible.
- If the demo API requires a bearer token, use the project's intended secure local/demo configuration. Do not invent a client-side secret-storage scheme.
- Do not expose a privileged admin token to an untrusted public browser. If the current demo uses a shared admin token, understand the deployment boundary and document the limitation.
- Never let the UI decide authorization.
- Never let the UI change a `DENY` into `ALLOW`.
- Never let the UI directly call the GitHub write endpoint.
- Never call `close_issue_with_note` from browser code.
- The only write path must remain the existing TrustRail backend approval / transaction flow.
- UI confirmation is not a substitute for backend approval binding and PRECHECK.
- Treat GitHub issue bodies and tool results as untrusted text. Render them as text, never as raw HTML.

### 7.6 State management

Keep it simple:
- Server data is fetched through the API client.
- Local state is limited to form input, filters, selected tabs, modal visibility, and polling state.
- Do not duplicate the backend transaction state machine in frontend logic.
- The UI may display known state transitions, but must not create or infer transitions.
- After approve / reject / retry / reconcile actions, re-fetch the authoritative transaction.
- Use optimistic UI only for harmless local interactions; never optimistically mark an approval or write as successful.

### 7.7 Polling

The product plan calls for polling instead of WebSockets.

- Start with a 1-second interval only for active run / transaction views where near-live feedback materially improves the demo.
- Stop polling when the run reaches a terminal state or the user leaves the page.
- Avoid polling every endpoint globally.
- Prevent overlapping requests.
- Show `Last updated` so the user knows the UI is live.
- Back off or pause on repeated server errors.
- Do not interpret a polling timeout as a transaction failure.

---

## 8. Interaction and behavior standards

### 8.1 Buttons

- Primary: one clear primary action per panel.
- Secondary: neutral surface / border.
- Destructive: red, with confirmation for consequential actions.
- Disabled buttons must explain why when the reason is not obvious.
- All asynchronous actions show loading state and prevent duplicate submission.

### 8.2 Confirmation dialogs

Use for:
- Approving a transaction.
- Rejecting a transaction if rejection is irreversible or consequential.
- Resetting the demo.
- Enabling fault injection / switching fault mode when it affects a live sandbox.

A confirmation must summarize the exact action and target. Do not use vague text such as `Are you sure?`.

### 8.3 Forms

- Labels above controls.
- Helpful examples in placeholder / helper text, not as the only label.
- Inline validation.
- Preserve user input after API validation errors.
- Disable submit while processing.
- Show backend validation messages in a readable way.

### 8.4 Tables

- Sticky headers for long tables.
- Compact but readable row height.
- Clear hover and selected states.
- Truncate long IDs with a copy / reveal affordance.
- Keep decision and state columns visible.
- On small screens, convert to stacked records or allow controlled horizontal scrolling; do not crush columns until unreadable.

### 8.5 Motion

- Use subtle 120–180 ms transitions for hover, menus, and panel changes.
- Use a restrained progress indicator for actual work in progress.
- Do not animate status colors continuously.
- Respect `prefers-reduced-motion`.
- Never animate `INDETERMINATE` as if it were a successful completion.

### 8.6 Notifications

Use toast notifications only for transient confirmation:
- `Policy compiled`
- `Run started`
- `Approval submitted`
- `Ledger verification completed`

Important state changes must also be visible in the page itself. Do not rely on a toast as the only record of an approval, rejection, or transaction outcome.

---

## 9. Empty, loading, and error states

These states are part of the product, not polish to postpone.

### Empty states
- No policies: explain how to compile a policy.
- No runs: explain how to start an agent run.
- No pending approvals: show `No approvals waiting`.
- No ledger events: explain that events appear after TrustRail records workflow activity.
- No test results: show `Not run yet`, not `Passed`.

### Loading states
- Use skeleton rows / panels for data fetches.
- Use specific button labels such as `Compiling…`, `Starting run…`, `Submitting approval…`, `Verifying…`.
- Preserve already loaded data during background refresh where safe.

### Error states
- API unavailable: show backend connectivity error and retry.
- Validation error: show the field / schema issue.
- Unauthorized: explain that the configured demo session is not authorized.
- Conflict / stale approval: show the invalidation reason and refresh current evidence.
- Unknown execution outcome: show `INDETERMINATE`, not a generic red error.
- Ledger verification failure: show a persistent integrity warning.

Never leave a blank panel or an endless spinner.

---

## 10. Responsive behavior

Desktop is the primary hackathon demo target, but the application should remain usable on a laptop and tablet.

- Desktop (≥ 1200 px): full sidebar and multi-column panels.
- Tablet (768–1199 px): collapsible sidebar; reduce dashboard columns.
- Mobile (< 768 px): top navigation / drawer, single-column cards, stacked forms, horizontally scrollable tables where necessary.
- Keep approval action buttons easy to reach.
- Keep the state label visible without requiring hover.
- JSON and hash panels should wrap or scroll internally rather than expanding the entire page.

Do not spend hackathon time building a separate mobile visual experience. Preserve functional readability.

---

## 11. Accessibility and usability

- Meet WCAG AA contrast for text and interactive controls where practical.
- Use semantic HTML (`button`, `nav`, `main`, `header`, `table`, `label`, etc.).
- Every input has a programmatic label.
- Every icon-only button has an accessible name.
- Keyboard navigation must work for navigation, dialogs, tabs, and actions.
- Focus indicators must be visible.
- Dialogs must trap focus and return focus to the trigger.
- Status must include text, not color alone.
- Respect reduced motion.
- Do not use color as the only difference between `DENY`, `INDETERMINATE`, and `APPROVAL_INVALIDATED`.

---

## 12. Images, illustrations, and visual assets

TrustRail is a data-heavy developer tool. **Use very few raster images.** Most visuals should be custom SVG diagrams, icons, timelines, and data visualizations.

### Use
- Original TrustRail SVG mark.
- GitHub mark for repository integration.
- Otari official mark only if a valid asset is available.
- Small architecture / workflow diagram made with SVG or HTML.
- State-machine visualization using nodes and connectors.
- Hash-chain visualization using connected event blocks.
- Scenario evidence diagrams / comparison tables.

### Do not use
- Stock photos of people in offices.
- AI robot illustrations.
- Random abstract gradient backgrounds.
- Generic shield / lock stock art.
- Screenshots of third-party dashboards as decoration.
- Unlicensed brand assets.
- Large hero illustrations that push the working console below the fold.

### Recommended custom visuals

1. **TrustRail workflow rail:** a horizontal or vertical sequence of policy, agent, authorization, approval, execution, reconciliation, ledger.
2. **Transaction state machine:** nodes with exact backend enum labels and allowed transitions. Use it as an explanatory visualization, not a source of state.
3. **Hash-chain ledger:** event blocks connected by previous-hash links.
4. **Reconciliation evidence panel:** simple visual showing `closed` + `marker_count` → evidence-based classification.
5. **Cross-model comparison:** a compact table showing different model proposals and identical deterministic enforcement outcomes.

All diagrams must reflect actual backend behavior. Do not add an edge, state, or guarantee that is not implemented.

---

## 13. Data visualization guidance

Use charts only when they clarify evidence.

Good candidates:
- Decision distribution for a dry run.
- Scenario pass / fail matrix.
- Cross-model outcomes.
- Run activity over time, if timestamps and enough records exist.

Avoid:
- Decorative pie charts.
- Fake live metrics.
- Arbitrary “Trust score” or “AI safety score”.
- A single percentage that suggests TrustRail can guarantee safety.
- Charts based on hardcoded demo numbers presented as live data.

For the cross-model story, a table is usually better than a chart: model behavior differs, deterministic policy enforcement remains the boundary.

---

## 14. Product copy and terminology

Use exact backend terms where correctness matters. Add plain-English explanations next to them.

Preferred wording:
- `Agent proposal` — not `Agent decision`.
- `Authorization decision` — not `AI approval`.
- `Requires human approval` — not `Approved`.
- `Approval invalidated` — not `Approval failed`.
- `Indeterminate outcome` — not `Unknown error`.
- `Read-only reconciliation probe` — not `Retry`.
- `Ledger verification` — not `Blockchain verification`.
- `Evidence-based reconciliation` — not `Exactly-once execution`.

Suggested product copy:
- Overview: `See what agents propose, what policy permits, and what evidence confirms.`
- Policy: `Define the rules. TrustRail's deterministic engine enforces them.`
- Runs: `The agent can propose. It cannot authorize a write.`
- Approvals: `Review the exact action and evidence before authorizing dispatch.`
- Ledger: `Every important decision and transaction event leaves an auditable record.`
- Indeterminate: `The response did not confirm the outcome. TrustRail will verify before any retry.`
- Reconciliation success: `GitHub evidence confirms the action was applied.`
- Not executed: `The probe found no transaction marker. A fresh approval is required before retry.`

Avoid claims such as:
- `Prompt injection solved`.
- `Exactly-once execution`.
- `Guaranteed safe AI`.
- `Blockchain ledger`.
- `Unbreakable audit trail`.
- `Approval cannot be bypassed` unless the statement is scoped to the implemented backend path and its limitations.

---

## 15. Recommended implementation order

Time is limited. Build the smallest complete product flow before secondary pages.

### Phase 1 — Foundation
- [ ] Inspect the existing repository and current frontend status before creating files.
- [ ] Inspect FastAPI `/openapi.json` and confirm the current route / schema contracts.
- [ ] Set up React + Vite + TypeScript if not already present.
- [ ] Add global CSS tokens and typography.
- [ ] Build TrustRail mark and application shell.
- [ ] Add centralized typed API client and error handling.
- [ ] Confirm backend health indicator works.

### Phase 2 — Core demo path
- [ ] Policy compilation form.
- [ ] Successful policy result and ambiguity / validation state.
- [ ] Dry-run results table and aggregate decision counts.
- [ ] Run creation form.
- [ ] Run status / proposal list.
- [ ] Transaction details.
- [ ] Approval review and confirmation.
- [ ] Transaction state updates using polling.
- [ ] Indeterminate / reconciliation evidence panel.
- [ ] Ledger event timeline.

### Phase 3 — Proof and polish
- [ ] Ledger verification.
- [ ] Trust Tests scenario list and evidence.
- [ ] Demo fault controls, only if backed by real endpoints.
- [ ] Overview dashboard.
- [ ] Responsive layout.
- [ ] Empty, loading, and error states.
- [ ] Accessibility and keyboard pass.
- [ ] Rehearse the five-minute demo without using the terminal for the main workflow.

### Priority if time becomes extremely limited

Build in this order:
1. Policy compile + dry run.
2. Run + proposal decisions.
3. Approval.
4. Transaction state / lost-response reconciliation.
5. Ledger timeline + verification.
6. Trust Tests.
7. Overview polish / integrations.

A complete, honest end-to-end flow is more valuable than seven attractive but disconnected screens.

---

## 16. Frontend acceptance checklist

A frontend feature is complete only when the relevant items pass:

### Visual consistency
- [ ] Uses shared tokens, typography, spacing, and component patterns.
- [ ] Uses semantic status colors consistently.
- [ ] No random gradients, stock art, or inconsistent icon families.
- [ ] Works at desktop and tablet widths.

### Backend correctness
- [ ] Uses a real documented backend endpoint.
- [ ] Request and response types match the current Pydantic / OpenAPI schema.
- [ ] Loading, validation, network, and server errors are handled.
- [ ] No frontend-generated authorization decision.
- [ ] No fabricated success state or metric.

### Security
- [ ] No secrets in browser code or Vite-exposed environment variables.
- [ ] No direct GitHub write calls from the browser.
- [ ] No ability to bypass approval or PRECHECK.
- [ ] Untrusted issue content is rendered safely as text.
- [ ] Consequential actions require explicit confirmation.

### Trust semantics
- [ ] `DENY`, `FAILED`, `FAILED_SAFE`, `INDETERMINATE`, `APPROVAL_INVALIDATED`, `UNRESOLVED`, and `DUPLICATE_DETECTED` remain distinct.
- [ ] `INDETERMINATE` is never displayed as success or as a normal failure.
- [ ] Reconciliation displays actual probe evidence.
- [ ] Ledger verification displays the backend's actual result.
- [ ] The UI never claims exactly-once execution.

### Demo readiness
- [ ] A user can follow the main flow without opening a terminal.
- [ ] The most important state changes are visible on screen.
- [ ] Polling stops when work is complete.
- [ ] No blank screens or endless loading states.
- [ ] The lost-response scene is understandable without narration.

---

## 17. Instructions for AI coding assistants

When asked to implement any TrustRail frontend feature, follow these instructions:

1. Read this document first and treat it as the frontend design source of truth.
2. Inspect the existing frontend code before changing architecture or creating files.
3. Read the current backend README and inspect FastAPI OpenAPI (`/openapi.json`) for the exact API contract.
4. Treat the current Python backend implementation as authoritative. The older Go-oriented hackathon build plan describes product intent, not the language or exact implementation details of the current backend.
5. Do not invent endpoints, request fields, response fields, state transitions, metrics, or capabilities.
6. Do not duplicate authorization, approval binding, transaction execution, or reconciliation logic in TypeScript.
7. Keep the visual design aligned with the tokens, state colors, layout, and component rules in this document.
8. Reuse existing components before introducing new ones.
9. Use real backend data. If an endpoint does not exist, clearly report the missing backend dependency rather than faking the feature.
10. Preserve the distinction between agent proposal, deterministic authorization, human approval, execution, reconciliation, and ledger evidence.
11. Do not add dependencies unless they materially reduce implementation time or complexity.
12. After implementation, run the available frontend lint / typecheck / build commands and report exactly what passed and failed.

### Feature implementation prompt template

```text
Implement [FEATURE] in the TrustRail frontend.

Before coding:
1. Read docs/FRONTEND_DESIGN.md.
2. Inspect the existing frontend structure and reuse its patterns.
3. Inspect the current FastAPI OpenAPI schema and backend README.
4. Confirm the exact endpoint, request schema, response schema, and error shape.
5. If the backend does not expose the required capability, do not mock it as real; report the missing dependency.

Implementation requirements:
- Follow the TrustRail design tokens and semantic state colors.
- Use typed API integration through the centralized API client.
- Keep authorization and transaction logic in the backend.
- Preserve exact transaction / decision states.
- Implement loading, empty, validation, and error states.
- Keep the UI responsive and accessible.
- Do not expose secrets or call GitHub write tools directly from the browser.

After coding:
- Run typecheck, lint, and production build.
- Summarize files changed, API contracts used, and verification results.
```

---

## 18. Final design principle

TrustRail should look like a system that takes responsibility for the consequences of agent actions.

The interface should never hide uncertainty, blur the boundary between an LLM and deterministic authorization, or make a dangerous action look like an ordinary button click.

**The visual narrative is the product narrative:**

`Propose → Verify → Decide → Approve → Dispatch → Reconcile → Prove`

Every screen should strengthen that story.