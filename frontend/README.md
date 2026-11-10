# TrustRail frontend

The frontend exposes two control-plane screens:

- **Run** starts a backend-owned agent run, polls its read-only status, displays
  persisted ledger activity and proposals, and sends approval/rejection decisions
  through the transaction API.
- **Policies** compiles, dry-runs, and explicitly activates policies.

The Run screen uses these backend endpoints:

- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/transactions/{transaction_id}/approve`
- `POST /api/v1/transactions/{transaction_id}/reject`
- `POST /api/v1/transactions/{transaction_id}/retry`

The deployment uses fixed Otari routing policies for now: `trustrail-compiler`
for policy compilation and `trustrail-planner` for agent runs. They are shown
for visibility only; the user cannot select a model from the frontend.

Approval is never treated as execution success in the browser. The existing
backend retry endpoint performs the final policy/fact precheck and owns the
write outcome, including approval invalidation and indeterminate execution.
