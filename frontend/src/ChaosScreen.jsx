import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from './lib/api/client'
import { chaosApi } from './lib/api/chaos'
import { usePolling } from './hooks/usePolling'

const FAULT_INFO = {
  none: ['No fault', 'Normal MCP operation.'],
  fail_before_apply: ['Fail before apply', 'The server fails before creating a comment.'],
  partial: ['Partial failure', 'The comment is created, then the close response fails.'],
  drop_after_apply: ['Drop response after apply', 'The write completes but its response is lost.'],
  delay_after_apply: ['Delay after apply', 'The write completes before the response is delayed.'],
}

function ErrorMessage({ error }) {
  return error ? <div className="alert error">{error instanceof ApiError ? error.message : error.message || 'Request failed.'}</div> : null
}

function ResultCard({ title, run, onApprove, busy }) {
  const transaction = run?.transaction
  if (!run) return <article className="chaos-result muted"><span>{title}</span><strong>Waiting for demo</strong></article>
  return <article className="chaos-result"><div className="result-title"><span>{title}</span><b className={`result-${String(transaction?.status || '').toLowerCase()}`}>{transaction?.status || 'UNKNOWN'}</b></div><dl><div><dt>Issue state</dt><dd>{run.issue?.state?.toUpperCase() || '—'}</dd></div><div><dt>Markers</dt><dd>{run.issue?.marker_count ?? '—'}</dd></div><div><dt>Comments</dt><dd>{run.issue?.total_comments ?? '—'}</dd></div><div><dt>Transaction</dt><dd><code>{transaction?.id || '—'}</code></dd></div></dl>{transaction?.status === 'PENDING_APPROVAL' && <button className="primary" disabled={busy} onClick={() => onApprove(transaction)}>{busy ? 'Approving…' : 'Approve & execute →'}</button>}</article>
}

export default function ChaosScreen() {
  const [status, setStatus] = useState(null)
  const [issues, setIssues] = useState([])
  const [issueNumber, setIssueNumber] = useState('')
  const [fault, setFault] = useState('none')
  const [executor, setExecutor] = useState('secure')
  const [note, setNote] = useState('TrustRail Chaos Lab controlled write')
  const [issueState, setIssueState] = useState(null)
  const [run, setRun] = useState(null)
  const [naiveRun, setNaiveRun] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const reconciledTransactions = useRef(new Set())
  const activeRun = [run, naiveRun].find((item) => ['INDETERMINATE', 'RECONCILING'].includes(item?.transaction?.status))
  const activeRunId = activeRun?.run_id
  const poll = usePolling(({ signal }) => chaosApi.getRun(activeRunId, { signal }), { enabled: Boolean(activeRunId), intervalMs: 1200, stopWhen: (result) => !['INDETERMINATE', 'RECONCILING'].includes(result.transaction?.status) })

  useEffect(() => {
    Promise.all([chaosApi.status(), chaosApi.issues()]).then(([configuration, available]) => { setStatus(configuration); setFault(configuration.fault_mode); setIssues(available.issues); if (available.issues[0]) setIssueNumber(String(available.issues[0].number)) }).catch(setError)
  }, [])
  useEffect(() => { if (issueNumber) chaosApi.issueState(issueNumber).then(setIssueState).catch(setError) }, [issueNumber])
  useEffect(() => {
    if (!poll.data) return
    const target = run?.run_id === poll.data.run_id ? 'safe' : naiveRun?.run_id === poll.data.run_id ? 'naive' : null
    if (target === 'safe') setRun(poll.data)
    if (target === 'naive') setNaiveRun(poll.data)

    const transaction = poll.data.transaction
    if (transaction?.status !== 'INDETERMINATE' || reconciledTransactions.current.has(transaction.id)) return
    reconciledTransactions.current.add(transaction.id)
    setBusy(true)
    chaosApi.reconcile(transaction.id)
      .then(() => chaosApi.getRun(poll.data.run_id))
      .then((result) => {
        if (target === 'safe') setRun(result)
        if (target === 'naive') setNaiveRun(result)
        setIssueState(result.issue)
      })
      .catch(setError)
      .finally(() => setBusy(false))
  }, [poll.data, run?.run_id, naiveRun?.run_id])

  const selectedIssue = useMemo(() => issues.find((item) => String(item.number) === String(issueNumber)), [issues, issueNumber])
  async function configureFault(event) {
    const mode = event.target.value
    setFault(mode); setError(null)
    try { await chaosApi.fault(mode); setStatus((current) => ({ ...current, fault_mode: mode })) } catch (caught) { setError(caught) }
  }
  async function executeDemo() {
    if (!issueNumber || busy) return
    if (executor === 'naive' && !window.confirm('Naive execution intentionally demonstrates unsafe retry behavior and may create duplicate GitHub comments. Continue?')) return
    setBusy(true); setError(null)
    try {
      const result = await chaosApi.run({ issue_number: Number(issueNumber), note, executor })
      if (executor === 'naive') setNaiveRun(result); else setRun(result)
      setIssueState(result.issue)
    } catch (caught) { setError(caught) } finally { setBusy(false) }
  }
  async function approveAndExecute(currentRun) {
    if (!currentRun?.transaction?.id || busy) return
    setBusy(true); setError(null)
    try {
      await chaosApi.approve(currentRun.transaction.id)
      const result = await chaosApi.retry(currentRun.transaction.id)
      if (currentRun.run_id === run?.run_id) setRun((current) => ({ ...current, transaction: result, issue: current.issue }))
      else setNaiveRun((current) => ({ ...current, transaction: result, issue: current.issue }))
      setIssueState(await chaosApi.issueState(Number(issueNumber)))
    } catch (caught) { setError(caught) } finally { setBusy(false) }
  }
  async function resetDemo() {
    if (!window.confirm(`Reset sandbox issue #${issueNumber}? This reopens the issue and removes TrustRail demo markers.`)) return
    setBusy(true); setError(null)
    try { const result = await chaosApi.reset(Number(issueNumber)); setRun(null); setNaiveRun(null); reconciledTransactions.current.clear(); setIssueState(result.issue) } catch (caught) { setError(caught) } finally { setBusy(false) }
  }
  async function refresh() { try { setIssueState(await chaosApi.issueState(Number(issueNumber))) } catch (caught) { setError(caught) } }

  return <main className="chaos-shell"><section className="chaos-hero"><div><p className="eyebrow">CHAOS LAB / CONTROLLED DEMONSTRATION</p><h1>Break it safely.</h1><p>Inject a real MCP fault, compare naive retries with TrustRail's transaction-controlled executor, and inspect the evidence.</p></div><span className="security-note"><span className="status-dot" /> Sandbox controls only</span></section>
    <ErrorMessage error={error} />
    <section className="chaos-grid"><article className="panel chaos-target"><div className="panel-heading"><div><p className="eyebrow">TARGET GITHUB ISSUE</p><h2>{status?.repository || 'Configured repository'}</h2></div><button className="quiet" onClick={refresh} disabled={!issueNumber}>Refresh</button></div><select value={issueNumber} onChange={(event) => setIssueNumber(event.target.value)}>{issues.map((issue) => <option key={issue.number} value={issue.number}>#{issue.number} — {issue.title}</option>)}</select><div className="chaos-state">{[['STATE', issueState?.state?.toUpperCase() || selectedIssue?.state?.toUpperCase() || '—'], ['COMMENTS', issueState?.total_comments ?? '—'], ['MARKERS', issueState?.marker_count ?? '—'], ['PROBED', issueState?.probed_at ? new Date(issueState.probed_at).toLocaleTimeString() : '—']].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div></article>
      <article className="panel chaos-config"><div className="panel-heading"><div><p className="eyebrow">FAULT INJECTION</p><h2>Choose the failure</h2></div><span className="state-badge">{fault === 'none' ? 'NO FAULT' : 'INJECTED'}</span></div><select value={fault} onChange={configureFault}>{(status?.fault_modes || Object.keys(FAULT_INFO).map((value) => ({ value }))).map((mode) => <option key={mode.value} value={mode.value}>{FAULT_INFO[mode.value]?.[0] || mode.label}</option>)}</select><p className="muted">{FAULT_INFO[fault]?.[1]}</p><small className="config-confirmation">Backend mode: <code>{status?.fault_mode || fault}</code></small></article></section>
    <section className="panel chaos-controls"><div className="panel-heading"><div><p className="eyebrow">EXECUTOR MODE</p><h2>Who controls the write?</h2></div><span className={`mode-flag ${executor === 'naive' ? 'unsafe' : 'safe'}`}>{executor === 'naive' ? 'UNSAFE DEMO' : 'SAFE PATH'}</span></div><div className="executor-toggle"><button className={executor === 'secure' ? 'selected' : ''} onClick={() => setExecutor('secure')}><b>SAFE EXECUTOR</b><span>Single controlled dispatch, reconciliation, no blind retry.</span></button><button className={executor === 'naive' ? 'selected unsafe' : ''} onClick={() => setExecutor('naive')}><b>NAIVE EXECUTOR</b><span>Demonstration only. May create duplicate comments.</span></button></div>{executor === 'naive' && <div className="alert warning-alert">Naive mode is explicitly opt-in and remains restricted to the configured demo environment.</div>}<textarea className="chaos-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={5000} /><div className="chaos-actions"><button className="primary chaos-run" onClick={executeDemo} disabled={busy || !issueNumber}>{busy ? 'Running controlled demo…' : 'Run demo →'}</button><button className="quiet" onClick={resetDemo} disabled={busy || !issueNumber}>Reset sandbox</button></div></section>
    <section className="panel"><div className="panel-heading"><div><p className="eyebrow">OBSERVED OUTCOME</p><h2>Naive versus TrustRail</h2></div><span className="muted">Actual GitHub evidence</span></div><div className="chaos-results"><ResultCard title="TrustRail safe execution" run={run} onApprove={() => approveAndExecute(run)} busy={busy} /><ResultCard title="Naive demonstration" run={naiveRun} onApprove={() => approveAndExecute(naiveRun)} busy={busy} /></div></section>
  </main>
}
