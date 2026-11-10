import { useEffect, useMemo, useState } from 'react'
import { ApiError } from './lib/api/client'
import { runApi } from './lib/api/runs'
import { usePolling } from './hooks/usePolling'

const EXAMPLE = 'Find open issues in the configured repository that have been inactive for more than 30 days and propose closing eligible issues with a note.'
const TERMINAL_RUN_STATES = new Set(['COMPLETED', 'FAILED'])
const APPROVAL_STATE = 'PENDING_APPROVAL'

function ErrorMessage({ error }) {
  if (!error) return null
  return <div className="alert error">{error instanceof ApiError ? error.message : error.message || 'Request failed.'}</div>
}

function DecisionBadge({ decision }) {
  const label = decision || 'PENDING'
  return <span className={`decision decision-${label.toLowerCase()}`}>{label}</span>
}

function ProposalCard({ proposal, onDecision, busy }) {
  const invalidated = proposal.status === 'APPROVAL_INVALIDATED'
  const actionable = proposal.status === APPROVAL_STATE && !invalidated
  const issueNumber = proposal.args?.issue_number
  const note = proposal.args?.note

  return (
    <article className={`proposal-card ${invalidated ? 'proposal-invalidated' : ''}`}>
      {invalidated && <div className="invalidation-banner"><strong>Approval no longer valid</strong><span>{proposal.approval_invalidation_reason || 'TrustRail blocked execution because the approval could not be revalidated.'}</span><small>Execution was blocked{proposal.id ? ` · Transaction ${proposal.id}` : ''}.</small></div>}
      <div className="proposal-header">
        <div><p className="eyebrow">PROPOSAL / #{issueNumber || '—'}</p><h3>{proposal.facts?.title || `Issue #${issueNumber || 'unknown'}`}</h3></div>
        <DecisionBadge decision={proposal.authorization_decision} />
      </div>
      <div className="proposal-meta"><span>{proposal.facts?.repository || 'Configured repository'}</span><span>{proposal.tool || 'Action proposal'}</span><span className="status-text">{proposal.status}</span></div>
      {note && <p className="proposal-note"><b>Proposed note</b>{note}</p>}
      <div className="reason-list"><b>Authorization reasons</b>{(proposal.authorization_reasons || ['No reasons returned by the backend.']).map((reason) => <span key={reason}>{reason}</span>)}</div>
      <div className="proposal-footer"><span>Transaction <code>{proposal.id}</code></span>{actionable && <div className="proposal-actions"><button className="quiet danger-button" disabled={busy} onClick={() => onDecision(proposal, 'reject')}>Reject</button><button className="primary" disabled={busy} onClick={() => onDecision(proposal, 'approve')}>{busy ? 'Processing…' : 'Approve & execute'}</button></div>}</div>
      {proposal.status === 'INDETERMINATE' && <div className="alert warning-alert">Execution outcome is uncertain. Reconcile this transaction before retrying.</div>}
    </article>
  )
}

function ActivityFeed({ events }) {
  if (!events?.length) return <div className="empty-feed">Activity will appear here as the backend records it.</div>
  return <ol className="activity-feed">{events.map((event) => <li key={event.id}><span className="activity-dot" /><div><b>{event.type.replaceAll('_', ' ')}</b><p>{event.payload?.message || event.payload?.tool_name || event.payload?.decision || 'Ledger event recorded.'}</p><time>{new Date(event.ts).toLocaleTimeString()}</time></div></li>)}</ol>
}

export default function RunScreen() {
  const [requestText, setRequestText] = useState('')
  const [run, setRun] = useState(null)
  const [startError, setStartError] = useState(null)
  const [starting, setStarting] = useState(false)
  const [decisionError, setDecisionError] = useState(null)
  const [busyProposal, setBusyProposal] = useState(null)

  const active = Boolean(run && !TERMINAL_RUN_STATES.has(run.status))
  const poll = usePolling(({ signal }) => runApi.get(run.id, { signal }), {
    enabled: active,
    intervalMs: 1000,
    stopWhen: (result) => TERMINAL_RUN_STATES.has(result.status),
  })

  useEffect(() => {
    if (poll.data) setRun(poll.data)
  }, [poll.data])

  const pendingCount = useMemo(() => (run?.proposals || []).filter((item) => item.status === APPROVAL_STATE).length, [run])

  async function startRun(event) {
    event.preventDefault()
    if (!requestText.trim() || starting) return
    setStarting(true)
    setStartError(null)
    setDecisionError(null)
    try {
      const created = await runApi.start(requestText.trim())
      setRun(created)
    } catch (error) {
      setStartError(error)
    } finally {
      setStarting(false)
    }
  }

  async function decide(proposal, action) {
    setBusyProposal(proposal.id)
    setDecisionError(null)
    try {
      if (action === 'approve') {
        await runApi.approve(proposal.id, 'console-operator')
        await runApi.execute(proposal.id)
      } else {
        await runApi.reject(proposal.id, 'console-operator')
      }
      const refreshed = await runApi.get(run.id)
      setRun(refreshed)
    } catch (error) {
      setDecisionError(error)
      try { setRun(await runApi.get(run.id)) } catch { /* retain the backend error */ }
    } finally {
      setBusyProposal(null)
    }
  }

  return <main className="run-shell">
    <section className="run-hero"><div><p className="eyebrow">AGENT OPERATIONS / EXECUTION CONSOLE</p><h1>Run with control.</h1><p>Submit an intent, observe the planner's trusted activity, and approve only the actions that remain valid.</p></div><div className="security-note"><span className="status-dot" /> Backend authorization enforced</div></section>
    <form className="panel run-composer" onSubmit={startRun}>
      <div className="panel-heading"><div><p className="eyebrow">RUN REQUEST</p><h2>What should the agent investigate?</h2><p className="muted">The planner can read configured GitHub facts and propose actions. It cannot execute a write without TrustRail authorization.</p></div><span className="state-badge">READ + PROPOSE</span></div>
      <textarea value={requestText} onChange={(event) => setRequestText(event.target.value)} placeholder={EXAMPLE} maxLength={10000} disabled={starting} />
      <div className="run-form-footer"><div className="model-visibility"><span>Planner model</span><strong>trustrail-planner</strong><small>Configured routing policy</small></div><button className="primary run-button" disabled={starting || !requestText.trim()}>{starting ? 'Starting run…' : 'Start run →'}</button></div>
      <ErrorMessage error={startError} />
    </form>

    {!run && <section className="empty-run panel"><span className="empty-icon">01</span><h2>No active run</h2><p className="muted">Start with a natural-language request. The live feed and proposal cards will appear after the backend confirms the run.</p></section>}
    {run && <><section className="run-summary"><div><p className="eyebrow">RUN {run.run_id}</p><h2>{run.status === 'RUNNING' ? 'Planner is working…' : `Run ${run.status.toLowerCase()}`}</h2><p className="muted">{run.user_request}</p></div><div className="run-stat"><span>MODEL</span><b>{run.planner_model}</b></div><div className="run-stat"><span>PROPOSALS</span><b>{run.proposal_count}</b></div><div className="run-stat"><span>APPROVALS</span><b>{pendingCount}</b></div></section><div className="run-grid"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">LIVE ACTIVITY</p><h2>Trusted execution feed</h2></div><span className={`state-badge ${run.status === 'RUNNING' ? 'live' : ''}`}>{run.status}</span></div><ActivityFeed events={run.events} />{poll.error && <><ErrorMessage error={poll.error} /><button className="quiet" onClick={poll.refresh}>Retry read-only refresh</button></>}</section><section className="panel proposals-panel"><div className="panel-heading"><div><p className="eyebrow">PROPOSALS / {run.proposal_count}</p><h2>Authorization decisions</h2></div></div>{decisionError && <ErrorMessage error={decisionError} />}{run.proposals?.length ? run.proposals.map((proposal) => <ProposalCard key={proposal.id} proposal={proposal} busy={busyProposal === proposal.id} onDecision={decide} />) : <div className="empty-feed">No proposals have been persisted for this run.</div>}</section></div></>}
  </main>
}
