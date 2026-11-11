import { useCallback, useEffect, useState } from 'react'
import { ApiError } from './lib/api/client'
import { policyApi } from './lib/api/policies'
import RunScreen from './RunScreen'
import LedgerScreen from './LedgerScreen'
import ChaosScreen from './ChaosScreen'
import UsageScreen from './UsageScreen'
import './App.css'

const EXAMPLE = 'Allow the agent to close stale P2 and P3 issues in the configured repository when they have been inactive for at least 30 days. Require human approval before closing P1 issues. Never close issues with the security label.'

function ErrorMessage({ error }) {
  if (!error) return null
  return <div className="alert error">{error instanceof ApiError ? error.message : error.message || 'Request failed.'}</div>
}

function DecisionBadge({ decision }) {
  return <span className={`decision decision-${decision.toLowerCase()}`}>{decision}</span>
}

function App() {
  const [description, setDescription] = useState('')
  const [compiled, setCompiled] = useState(null)
  const [compileError, setCompileError] = useState(null)
  const [compiling, setCompiling] = useState(false)
  const [dryRun, setDryRun] = useState(null)
  const [dryRunError, setDryRunError] = useState(null)
  const [runningDryRun, setRunningDryRun] = useState(false)
  const [activation, setActivation] = useState(null)
  const [activationError, setActivationError] = useState(null)
  const [activating, setActivating] = useState(false)
  const [active, setActive] = useState(null)
  const [screen, setScreen] = useState('policy')
  const [ledgerReady, setLedgerReady] = useState(false)

  useEffect(() => {
    policyApi.active().then((result) => {
      setActive(result)
    }).catch(() => {
      setActive(null)
    })
  }, [])

  async function compile() {
    if (!description.trim()) return
    setCompiling(true)
    setCompileError(null)
    setCompiled(null)
    setDryRun(null)
    setActivation(null)
    try {
      const result = await policyApi.compile(description.trim())
      if (result.error === 'ambiguous') {
        setCompiled({ ambiguous: true, questions: result.questions })
      } else {
        setCompiled(result)
      }
    } catch (error) {
      setCompileError(error)
    } finally {
      setCompiling(false)
    }
  }

  async function runDryRun() {
    if (!compiled?.policy) return
    setRunningDryRun(true)
    setDryRunError(null)
    try {
      setDryRun(await policyApi.dryRun(compiled.policy))
    } catch (error) {
      setDryRunError(error)
    } finally {
      setRunningDryRun(false)
    }
  }

  async function activate() {
    if (!compiled?.policy || !dryRun) return
    if (!window.confirm(`Activate policy version ${compiled.policy.version}?`)) return
    setActivating(true)
    setActivationError(null)
    setActivation(null)
    try {
      const result = await policyApi.activate(compiled.policy, description)
      setActivation(result)
      setActive(result)
      setScreen('run')
    } catch (error) {
      setActivationError(error)
    } finally {
      setActivating(false)
    }
  }

  const readyToReview = Boolean(compiled?.policy)
  const runReady = Boolean(active?.policy)

  const handleRunState = useCallback((run) => {
    if (!run) return
    const proposals = run.proposals || []
    const hasPendingApproval = proposals.some((proposal) => proposal.status === 'PENDING_APPROVAL')
    const allTerminal = proposals.length > 0 && proposals.every((proposal) => (
      ['SUCCEEDED', 'FAILED', 'FAILED_SAFE', 'REJECTED', 'DENIED', 'APPROVAL_INVALIDATED'].includes(proposal.status)
    ))
    setLedgerReady(run.status === 'COMPLETED' && allTerminal && !hasPendingApproval)
  }, [])

  return (
    <main className="policy-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">TR</span><span>TrustRail</span></div>
        <nav className="screen-nav" aria-label="Primary">
          <button className={screen === 'policy' ? 'nav-active' : ''} onClick={() => setScreen('policy')}>Policies</button>
          {runReady && <button className={screen === 'run' ? 'nav-active' : ''} onClick={() => setScreen('run')}>Run</button>}
          {ledgerReady && <button className={screen === 'ledger' ? 'nav-active' : ''} onClick={() => setScreen('ledger')}>Ledger</button>}
          <button className={screen === 'chaos' ? 'nav-active' : ''} onClick={() => setScreen('chaos')}>Chaos Lab</button>
          <button className={screen === 'usage' ? 'nav-active' : ''} onClick={() => setScreen('usage')}>Usage &amp; Budgets</button>
        </nav>
        <div className="status-pill"><span className="status-dot" /> Authorization console</div>
      </header>

      {screen === 'run' && runReady ? <RunScreen onViewUsage={() => setScreen('usage')} onRunStateChange={handleRunState} onViewLedger={() => setScreen('ledger')} /> : screen === 'ledger' && ledgerReady ? <LedgerScreen /> : screen === 'chaos' ? <ChaosScreen /> : screen === 'usage' ? <UsageScreen /> : <>
      <section className="hero-copy">
        <p className="eyebrow">POLICY MANAGEMENT / CONTROL PLANE</p>
        <h1>Authorise with intention.</h1>
        <p>Describe a policy, inspect the compiled artifact, test it against live issue facts, then activate it explicitly.</p>
      </section>

      <section className="workflow">
        <div className="step active"><span>01</span><b>Describe</b></div>
        <div className={`step ${readyToReview ? 'active' : ''}`}><span>02</span><b>Review</b></div>
        <div className={`step ${dryRun ? 'active' : ''}`}><span>03</span><b>Dry-run</b></div>
        <div className={`step ${activation ? 'active' : ''}`}><span>04</span><b>Activate</b></div>
      </section>

      <section className="panel editor-panel">
        <div className="panel-heading"><div><p className="eyebrow">POLICY AUTHORING</p><h2>What should the agent be allowed to do?</h2><p className="model-caption">Compiler model <strong>trustrail-compiler</strong></p></div><span className="state-badge">DRAFT</span></div>
        <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder={EXAMPLE} maxLength={10000} />
        <div className="editor-footer"><span>{description.length.toLocaleString()} / 10,000 characters</span><button className="primary" onClick={compile} disabled={compiling || !description.trim()}>{compiling ? 'Compiling…' : 'Compile policy →'}</button></div>
        <ErrorMessage error={compileError} />
      </section>

      {compiled?.ambiguous && <section className="panel warning-panel"><p className="eyebrow">CLARIFICATION REQUIRED</p><h2>The compiler needs more detail</h2><ul>{compiled.questions.map((question) => <li key={question}>{question}</li>)}</ul><p className="muted">Refine the description above and compile again. Nothing has been activated.</p></section>}

      {readyToReview && <section className="review-grid">
        <article className="panel summary-panel"><div className="panel-heading"><div><p className="eyebrow">COMPILED SUMMARY</p><h2>Human-readable controls</h2></div><span className="state-badge success">VALIDATED</span></div><p className="summary">{compiled.summary}</p><dl><div><dt>Repository</dt><dd>{compiled.policy.repo}</dd></div><div><dt>Policy version</dt><dd>v{compiled.policy.version}</dd></div><div><dt>Max actions / run</dt><dd>{compiled.policy.limits.max_actions_per_run}</dd></div></dl></article>
        <article className="panel json-panel"><div className="panel-heading"><div><p className="eyebrow">VALIDATED ARTIFACT</p><h2>Compiled JSON</h2></div><button className="quiet" onClick={() => navigator.clipboard.writeText(JSON.stringify(compiled.policy, null, 2))}>Copy JSON</button></div><pre>{JSON.stringify(compiled.policy, null, 2)}</pre></article>
      </section>}

      {readyToReview && <section className="panel dryrun-panel"><div className="panel-heading"><div><p className="eyebrow">READ-ONLY EVALUATION</p><h2>Test against current GitHub facts</h2><p className="muted">No transactions, approvals, writes, or policy changes are created.</p></div><button className="primary" onClick={runDryRun} disabled={runningDryRun}>{runningDryRun ? 'Evaluating…' : 'Run dry-run →'}</button></div><ErrorMessage error={dryRunError} />{dryRun && <><div className="metrics">{[['TOTAL', dryRun.summary.total_issues], ['ALLOW', dryRun.summary.allowed], ['APPROVAL', dryRun.summary.requires_approval], ['DENY', dryRun.summary.denied], ['INVALID', dryRun.summary.policy_invalid]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><div className="table-wrap"><table><thead><tr><th>Issue</th><th>Decision</th><th>Reasons</th></tr></thead><tbody>{dryRun.results.map((item) => <tr key={item.issue_number}><td><b>#{item.issue_number}</b><small>{item.title}</small></td><td><DecisionBadge decision={item.decision} /></td><td>{item.reasons.join(' ')}</td></tr>)}</tbody></table></div>{!dryRun.results.length && <p className="empty">No issues matched the returned facts.</p>}</>}</section>}

      {readyToReview && <section className="activation-row"><div><p className="eyebrow">EXPLICIT ACTIVATION</p><h2>Make this policy authoritative</h2><p className="muted">Activation changes the policy used by future agent proposals. It never executes a GitHub action.</p>{active?.policy && <p className="active-note">Active version: v{active.version} · {active.policy.repo}</p>}</div><div><button className="primary activate" onClick={activate} disabled={!dryRun || activating}>{activating ? 'Activating…' : dryRun ? `Activate v${compiled.policy.version}` : 'Run dry-run first'}</button><ErrorMessage error={activationError} />{activation && <div className="alert success-alert">Policy v{activation.version} is now active.</div>}</div></section>}
      </>}
    </main>
  )
}

export default App
