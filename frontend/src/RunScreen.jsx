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

function StatusBadge({ status }) {
  return <span className={`workflow-status status-${String(status || 'NOT_STARTED').toLowerCase()}`}>{String(status || 'NOT_STARTED').replaceAll('_', ' ')}</span>
}

function TechnicalActivity({ events }) {
  const [open, setOpen] = useState(false)
  return <details className="technical-activity" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>Technical activity <span>{events?.length || 0} events</span></summary>
    {!events?.length ? <p className="muted">No planner activity has been persisted yet.</p> : <ol className="activity-feed">{events.map((event) => <li key={event.id}><span className="activity-dot" /><div><b>{event.payload?.tool_name || event.type.replaceAll('_', ' ')}</b><p>{event.payload?.message || event.payload?.result_summary || event.payload?.decision || 'Ledger event recorded.'}</p><small>{new Date(event.ts).toLocaleTimeString()} · {event.id}</small></div></li>)}</ol>}
  </details>
}

function ProposalCard({ proposal, onDecision, busy }) {
  const invalidated = proposal.status === 'APPROVAL_INVALIDATED'
  const actionable = proposal.status === APPROVAL_STATE && !invalidated
  const issueNumber = proposal.args?.issue_number
  return <article className={`proposal-card ${invalidated ? 'proposal-invalidated' : ''}`}>
    {invalidated && <div className="invalidation-banner"><strong>Approval invalidated</strong><span>{proposal.approval_invalidation_reason || 'TrustRail blocked execution because approval could not be revalidated.'}</span></div>}
    <div className="proposal-header"><div><p className="eyebrow">UNTRUSTED CANDIDATE / #{issueNumber || '—'}</p><h3>{proposal.facts?.title || `Issue #${issueNumber || 'unknown'}`}</h3></div><StatusBadge status={proposal.authorization_decision || 'PENDING'} /></div>
    <div className="proposal-meta"><span>{proposal.facts?.repository || 'Configured repository'}</span><span>{proposal.tool || 'Action proposal'}</span><span>{proposal.status}</span></div>
    {proposal.args?.note && <p className="proposal-note"><b>Proposed note</b>{proposal.args.note}</p>}
    <div className="reason-list"><b>Backend decision reasons</b>{(proposal.authorization_reasons || ['No reasons returned by the backend.']).map((reason) => <span key={reason}>{reason}</span>)}</div>
    <div className="proposal-footer"><span>Transaction <code>{proposal.id}</code></span>{actionable && <div className="proposal-actions"><button className="quiet danger-button" disabled={busy} onClick={() => onDecision(proposal, 'reject')}>Reject</button><button className="primary" disabled={busy} onClick={() => onDecision(proposal, 'approve')}>{busy ? 'Processing…' : 'Approve & execute'}</button></div>}</div>
    {proposal.status === 'INDETERMINATE' && <div className="alert warning-alert">Outcome is uncertain. Reconciliation is required before retrying.</div>}
  </article>
}

function StageDetails({ stage }) {
  const details = stage.details || {}
  if (stage.id === 'planning') return <TechnicalActivity events={details.events} />
  if (stage.id === 'validation') return <div className="detail-grid"><div><span>Decision</span><strong><StatusBadge status={details.decision || 'PENDING'} /></strong></div><div><span>Policy</span><strong>{details.policy_id || 'Not evaluated'}{details.policy_version ? ` · v${details.policy_version}` : ''}</strong></div><div className="detail-wide"><span>Independent evaluations</span>{details.evaluations?.length ? details.evaluations.map((evaluation) => <div className="evaluation-row" key={evaluation.transaction_id}><strong><StatusBadge status={evaluation.decision || 'PENDING'} /></strong><code>{evaluation.transaction_id}</code><span>{evaluation.reasons?.join(' ') || 'No reasons returned.'}</span></div>) : <p className="muted">No evaluated proposal facts persisted.</p>}</div></div>
  if (stage.id === 'verification') return <div className="detail-grid"><div><span>Ledger integrity</span><strong><StatusBadge status={details.ledger_verification?.valid ? 'VERIFIED' : 'NOT_VERIFIED'} /></strong></div><div><span>Events checked</span><strong>{details.ledger_verification?.events_checked ?? 0}</strong></div><div><span>Ledger events</span><strong>{details.ledger_event_count ?? 0}</strong></div>{details.reconciliation?.length > 0 && <div className="detail-wide"><span>Reconciliation evidence</span><pre>{JSON.stringify(details.reconciliation, null, 2)}</pre></div>}</div>
  return <div className="detail-grid">{Object.entries(details).filter(([, value]) => value !== null && value !== undefined && value !== '').map(([key, value]) => <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</strong></div>)}</div>
}

function Workflow({ stages, proposals, onDecision, busy }) {
  return <section className="workflow-pipeline" aria-label="TrustRail execution workflow">
    <div className="workflow-intro"><div><p className="eyebrow">TRUSTRAIL EXECUTION PIPELINE</p><h2>From intent to verified outcome</h2></div><span className="pipeline-caption">Planner proposes <b>·</b> TrustRail decides <b>·</b> Ledger remembers</span></div>
    <div className="workflow-track">
      {stages.map((stage, index) => <article className={`workflow-stage stage-${stage.id} ${stage.id === 'validation' ? 'checkpoint' : ''}`} style={{ '--stage-delay': `${index * 140}ms` }} key={stage.id}>
        <div className="stage-connector" aria-hidden="true" />
        <div className="stage-body">
          <div className="stage-marker">{String(index + 1).padStart(2, '0')}</div>
          <div className="stage-heading"><div><p className="eyebrow">{stage.id === 'validation' ? 'SECURITY CHECKPOINT' : `STAGE ${String(index + 1).padStart(2, '0')}`}</p><h3>{stage.title}</h3></div><StatusBadge status={stage.status} /></div>
          <p className="stage-summary">{stage.summary}</p>
          <details className="stage-inspector"><summary>Inspect stage</summary><StageDetails stage={stage} /></details>
          {stage.id === 'proposal' && proposals?.map((proposal) => <ProposalCard key={proposal.id} proposal={proposal} onDecision={onDecision} busy={busy === proposal.id} />)}
        </div>
      </article>)}
    </div>
  </section>
}

export default function RunScreen() {
  const [requestText, setRequestText] = useState('')
  const [run, setRun] = useState(null)
  const [startError, setStartError] = useState(null)
  const [starting, setStarting] = useState(false)
  const [decisionError, setDecisionError] = useState(null)
  const [busyProposal, setBusyProposal] = useState(null)
  const active = Boolean(run && !TERMINAL_RUN_STATES.has(run.status))
  const poll = usePolling(({ signal }) => runApi.get(run.id, { signal }), { enabled: active, intervalMs: 1000, stopWhen: (result) => TERMINAL_RUN_STATES.has(result.status) })

  useEffect(() => { if (poll.data) setRun(poll.data) }, [poll.data])
  const pendingCount = useMemo(() => (run?.proposals || []).filter((item) => item.status === APPROVAL_STATE).length, [run])

  async function startRun(event) {
    event.preventDefault()
    if (!requestText.trim() || starting) return
    setStarting(true); setStartError(null); setDecisionError(null)
    try { setRun(await runApi.start(requestText.trim())) } catch (error) { setStartError(error) } finally { setStarting(false) }
  }

  async function decide(proposal, action) {
    setBusyProposal(proposal.id); setDecisionError(null)
    try {
      if (action === 'approve') { await runApi.approve(proposal.id, 'console-operator'); await runApi.execute(proposal.id) } else await runApi.reject(proposal.id, 'console-operator')
      setRun(await runApi.get(run.id))
      poll.refresh()
    } catch (error) { setDecisionError(error); try { setRun(await runApi.get(run.id)) } catch { /* preserve the backend error */ } } finally { setBusyProposal(null) }
  }

  return <main className="run-shell">
    <section className="run-hero"><div><p className="eyebrow">AGENT OPERATIONS / AUTHORIZATION WORKFLOW</p><h1>Run with control.</h1><p> The planner proposes. TrustRail validates. Humans approve when required. The controlled executor records the outcome.</p></div><div className="security-note"><span className="status-dot" /> Backend authorization enforced</div></section>
    <form className="panel run-composer" onSubmit={startRun}><div className="panel-heading"><div><p className="eyebrow">REQUEST COMPOSER</p><h2>What should the agent investigate?</h2><p className="muted">This request becomes the immutable run context. The planner can read and propose; it cannot authorize or execute writes.</p></div><span className="state-badge">READ + PROPOSE</span></div><textarea value={requestText} onChange={(event) => setRequestText(event.target.value)} placeholder={EXAMPLE} maxLength={10000} disabled={starting} /><div className="run-form-footer"><div className="model-visibility"><span>Planner model</span><strong>trustrail-planner</strong><small>Configured routing policy</small></div><button className="primary run-button" disabled={starting || !requestText.trim()}>{starting ? 'Starting run…' : 'Start run →'}</button></div><ErrorMessage error={startError} /></form>
    {!run && <section className="empty-run panel"><span className="empty-icon">01</span><h2>No active run</h2><p className="muted">Start with a natural-language request to see the complete authorization workflow.</p></section>}
    {run && <><section className="run-summary"><div><p className="eyebrow">RUN {run.run_id}</p><h2>{run.status === 'RUNNING' ? 'Planner is working…' : `Run ${run.status.toLowerCase()}`}</h2><p className="muted">{run.user_request}</p></div><div className="run-stat"><span>MODEL</span><b>{run.planner_model}</b></div><div className="run-stat"><span>PROPOSALS</span><b>{run.proposal_count}</b></div><div className="run-stat"><span>PENDING APPROVAL</span><b>{pendingCount}</b></div></section><div className="run-last-updated">{poll.isPolling ? 'Refreshing…' : poll.lastUpdated ? `Last updated ${poll.lastUpdated.toLocaleTimeString()}` : 'Read-only workflow projection'}</div>{decisionError && <ErrorMessage error={decisionError} />}{poll.error && <><ErrorMessage error={poll.error} /><button className="quiet" onClick={poll.refresh}>Retry read-only refresh</button></>}<Workflow stages={run.workflow?.stages || []} proposals={run.proposals} onDecision={decide} busy={busyProposal} /></>}
  </main>
}
