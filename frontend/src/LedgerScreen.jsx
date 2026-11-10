import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from './lib/api/client'
import { ledgerApi } from './lib/api/ledger'

const STATES = ['', 'PROPOSED', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'PRECHECK', 'APPROVAL_INVALIDATED', 'DISPATCHING', 'SUCCEEDED', 'FAILED', 'FAILED_SAFE', 'INDETERMINATE', 'NOT_EXECUTED', 'UNRESOLVED', 'DUPLICATE_DETECTED']

function ErrorMessage({ error }) {
  if (!error) return null
  return <div className="alert error">{error instanceof ApiError ? error.message : error.message || 'Request failed.'}</div>
}

function StateBadge({ state }) {
  return <span className={`ledger-state ledger-state-${state.toLowerCase()}`}>{state.replaceAll('_', ' ')}</span>
}

function CopyButton({ value }) {
  return <button className="copy-button" onClick={() => navigator.clipboard.writeText(value)} title="Copy identifier">Copy</button>
}

function Timestamp({ value }) {
  if (!value) return <span>—</span>
  return <time title={value}>{new Date(value).toLocaleString()}</time>
}

function EventItem({ event }) {
  const [expanded, setExpanded] = useState(false)
  return <li className="ledger-event">
    <div className="event-marker" />
    <div className="event-content">
      <button className="event-toggle" onClick={() => setExpanded(!expanded)}>
        <span><b>{event.type.replaceAll('_', ' ')}</b><small>{event.txn_id ? 'Transaction event' : 'Run event'} · Sequence {event.seq} · <Timestamp value={event.ts} /></small></span>
        <span className="event-chevron">{expanded ? '−' : '+'}</span>
      </button>
      <div className="event-hashes"><span>Prev <code>{event.prev_hash.slice(0, 12)}…</code></span><span>Hash <code>{event.hash.slice(0, 12)}…</code></span></div>
      {expanded && <pre className="event-metadata">{JSON.stringify(event.payload, null, 2)}</pre>}
    </div>
  </li>
}

function TransactionOverview({ transaction }) {
  const issueNumber = transaction.args?.issue_number
  const repository = transaction.facts?.repository || 'Configured repository'
  return <div className="ledger-overview-grid">
    {[['Transaction ID', transaction.id], ['Run ID', transaction.run_id], ['Repository', repository], ['Issue', issueNumber ? `#${issueNumber}` : '—'], ['Operation', transaction.tool], ['Authorization', transaction.authorization_decision || 'Not recorded'], ['Created', transaction.created_at], ['Updated', transaction.updated_at]].map(([label, value]) => <div key={label} className="overview-field"><span>{label}</span><strong>{['Created', 'Updated'].includes(label) ? <Timestamp value={value} /> : value}</strong>{typeof value === 'string' && label.endsWith('ID') && <CopyButton value={value} />}</div>)}
  </div>
}

function ReconciliationEvidence({ items }) {
  if (!items?.length) return <p className="muted">No reconciliation evidence has been recorded.</p>
  return <div className="evidence-list">{items.map((item) => <article key={item.event_id}><div><b>{item.outcome || item.restored_state || 'Probe attempt'}</b><span><Timestamp value={item.timestamp} /></span></div><p>{item.reason || item.error_code || 'Backend reconciliation evidence recorded.'}</p>{item.evidence && <dl>{Object.entries(item.evidence).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{Array.isArray(value) ? value.join(', ') : String(value)}</dd></div>)}</dl>}</article>)}</div>
}

function Detail({ transaction, onBack, onRefresh }) {
  const [verification, setVerification] = useState(null)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState(null)
  const events = useMemo(() => [...(transaction.run_events || []), ...(transaction.events || [])].sort((a, b) => new Date(a.ts) - new Date(b.ts)), [transaction])

  async function verify() {
    setVerifying(true)
    setError(null)
    try {
      setVerification(await ledgerApi.verify(transaction.id))
    } catch (requestError) {
      setError(requestError)
      setVerification(null)
    } finally {
      setVerifying(false)
    }
  }

  return <section className="ledger-detail">
    <button className="quiet back-button" onClick={onBack}>← Back to ledger</button>
    <div className="detail-heading"><div><p className="eyebrow">TRANSACTION DETAIL</p><h2>{transaction.args?.note || transaction.tool}</h2><p className="muted">{transaction.id}</p></div><StateBadge state={transaction.status} /></div>
    <section className="panel ledger-detail-panel"><div className="panel-heading"><div><p className="eyebrow">OVERVIEW</p><h2>Transaction record</h2></div><button className="quiet" onClick={onRefresh}>Refresh</button></div><TransactionOverview transaction={transaction} /><div className="detail-callout"><span>Otari request IDs</span>{transaction.otari_request_ids?.length ? transaction.otari_request_ids.map((id) => <div key={id}><code>{id}</code><CopyButton value={id} /></div>) : <p className="muted">No Otari request IDs recorded.</p>}</div></section>
    <section className="panel ledger-detail-panel"><div className="panel-heading"><div><p className="eyebrow">EVENT TIMELINE</p><h2>{events.length} persisted events</h2></div></div>{events.length ? <ol className="ledger-events">{events.map((event) => <EventItem key={`${event.id}-${event.seq}`} event={event} />)}</ol> : <p className="muted">No ledger events found for this transaction or run.</p>}</section>
    <section className="panel ledger-detail-panel"><div className="panel-heading"><div><p className="eyebrow">RECONCILIATION</p><h2>Probe evidence</h2></div></div><ReconciliationEvidence items={transaction.reconciliation} /></section>
    <section className={`panel verification-panel ${verification?.valid ? 'verified' : verification && !verification.valid ? 'verification-failed' : ''}`}><div><p className="eyebrow">CRYPTOGRAPHIC INTEGRITY</p><h2>{verification?.valid ? 'Ledger integrity verified' : verification && !verification.valid ? 'Ledger integrity verification failed' : 'Verification not performed'}</h2><p className="muted">{verification ? `${verification.events_checked} transaction events checked at ${new Date(verification.verified_at).toLocaleString()}.` : 'Verification is read-only and checks the backend-owned transaction hash chain.'}</p>{verification?.reason && <p className="verification-reason">{verification.reason}</p>}</div><button className="primary verify-button" onClick={verify} disabled={verifying}>{verifying ? 'Verifying…' : 'Verify ledger'}</button><ErrorMessage error={error} /></section>
  </section>
}

export default function LedgerScreen() {
  const [items, setItems] = useState([])
  const [selected, setSelected] = useState(null)
  const [search, setSearch] = useState('')
  const [state, setState] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await ledgerApi.transactions({ search, state, limit: 100 })
      setItems(result.items || [])
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }, [search, state])

  useEffect(() => { load() }, [load])
  async function openTransaction(item) {
    setError(null)
    try { setSelected(await ledgerApi.transaction(item.id)) } catch (requestError) { setError(requestError) }
  }

  const stats = useMemo(() => ({
    total: items.length,
    succeeded: items.filter((item) => item.status === 'SUCCEEDED').length,
    failed: items.filter((item) => ['FAILED', 'FAILED_SAFE'].includes(item.status)).length,
    uncertain: items.filter((item) => ['INDETERMINATE', 'UNRESOLVED'].includes(item.status)).length,
  }), [items])

  return <main className="ledger-shell">
    <section className="ledger-hero"><div><p className="eyebrow">AUDIT / APPEND-ONLY LEDGER</p><h1>Evidence you can verify.</h1><p>Inspect persisted transactions, trace their event history, and verify integrity against the backend hash chain.</p></div><button className="quiet" onClick={load}>Refresh ledger</button></section>
    {!selected ? <><section className="ledger-stats">{[['TOTAL', stats.total], ['SUCCEEDED', stats.succeeded], ['FAILED', stats.failed], ['UNCERTAIN', stats.uncertain]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</section><section className="panel ledger-table-panel"><div className="ledger-filters"><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && load()} placeholder="Search transaction, run, or operation…" /><select value={state} onChange={(event) => setState(event.target.value)}>{STATES.map((item) => <option key={item} value={item}>{item ? item.replaceAll('_', ' ') : 'All states'}</option>)}</select><button className="primary" onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Search'}</button></div><ErrorMessage error={error} />{loading && !items.length ? <div className="empty-feed">Loading persisted transactions…</div> : items.length ? <div className="table-wrap"><table className="ledger-table"><thead><tr><th>Transaction</th><th>Run</th><th>Action</th><th>State</th><th>Created</th><th>Updated</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} onClick={() => openTransaction(item)}><td><b>{item.id.slice(0, 14)}…</b><small>{item.facts?.repository || 'Configured repository'} · #{item.args?.issue_number || '—'}</small></td><td><code>{item.run_id.slice(0, 12)}…</code></td><td>{item.tool}</td><td><StateBadge state={item.status} /></td><td><Timestamp value={item.created_at} /></td><td><Timestamp value={item.updated_at} /></td></tr>)}</tbody></table></div> : <div className="empty-feed">No persisted transactions match this filter.</div>}</section></> : <Detail transaction={selected} onBack={() => setSelected(null)} onRefresh={() => openTransaction(selected)} />}
  </main>
}
