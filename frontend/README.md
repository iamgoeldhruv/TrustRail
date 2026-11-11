# TrustRail frontend

The frontend exposes two control-plane screens:

- **Run** starts a backend-owned agent run, polls its read-only status, displays
  persisted ledger activity and proposals, and sends approval/rejection decisions
  through the transaction API.
- **Ledger** lists persisted transactions, exposes run and transaction event
  timelines, stored Otari request IDs, reconciliation evidence, and a
  backend-authoritative hash-chain verification action.
- **Policies** compiles, dry-runs, and explicitly activates policies.
- **Usage & Budgets** displays live planner-key budget limits, usage, and spend series from TrustRail's backend.

Usage data is fetched server-side with `OTARI_AGENT_API_KEY`. The browser
never contacts Otari directly and no Otari credential is exposed in Vite
environment variables or API responses.

The Run screen uses these backend endpoints:

- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/transactions/{transaction_id}/approve`
- `POST /api/v1/transactions/{transaction_id}/reject`
- `POST /api/v1/transactions/{transaction_id}/retry`
- `GET /api/v1/integrations/otari/budget`
- `GET /api/v1/integrations/otari/usage`
- `GET /api/v1/integrations/otari/usage/series`
- `GET /api/v1/ledger/transactions`
- `GET /api/v1/ledger/transactions/{transaction_id}`
- `POST /api/v1/ledger/transactions/{transaction_id}/verify`

The deployment uses fixed Otari routing policies for now: `trustrail-compiler`
for policy compilation and `trustrail-planner` for agent runs. They are shown
for visibility only; the user cannot select a model from the frontend.

Approval is never treated as execution success in the browser. The existing
backend retry endpoint performs the final policy/fact precheck and owns the
write outcome, including approval invalidation and indeterminate execution.
