import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from './lib/api/client'
import { otariApi } from './lib/api/otari'

function ErrorMessage({ error }) {
  return error ? <div className="alert error">{error instanceof ApiError ? error.message : error.message || 'Request failed.'}</div> : null
}

function money(value) {
  return value == null ? '—' : `$${Number(value).toFixed(2)}`
}

function timestamp(value) {
  return value ? new Date(value).toLocaleString() : '—'
}

function BudgetStatus({ budget }) {
  if (!budget) return null
  const primary = budget.limits.find((limit) => limit.scope === 'api_token' && limit.limit_usd != null)
  const limit = primary?.limit_usd
  const used = primary?.used_usd
  const remaining = budget.remaining_usd
  const percent = limit && used != null ? Math.min(100, Math.max(0, (used / limit) * 100)) : null
  const state = !budget.budgets_enforced ? 'disabled' : remaining === 0 ? 'exhausted' : percent >= 80 ? 'warning' : 'healthy'
  return <article className={`budget-overview budget-${state}`}>
    <div className="budget-overview-heading"><div><p className="eyebrow">PLANNER BUDGET</p><h2>{money(used)}{limit != null ? ` spent of ${money(limit)}` : ' spent'}</h2></div><span className="state-badge">{state}</span></div>
    <div className="budget-meter"><span style={{ width: `${percent ?? 0}%` }} /></div>
    <div className="budget-summary"><strong>{money(remaining)} remaining</strong><span>{percent == null ? 'Limit not reported' : `${percent.toFixed(0)}% consumed`}</span></div>
    <p className="muted">{primary?.resets_at ? `Resets ${timestamp(primary.resets_at)}` : 'No reset time reported by Otari.'}</p>
    {!budget.budgets_enforced && <div className="alert warning-alert">Budget enforcement is disabled in Otari.</div>}
    {remaining === 0 && <div className="alert error">Planner budget exhausted. Otari may reject new inference requests.</div>}
  </article>
}

export function PlannerBudgetIndicator({ onViewUsage }) {
  const [budget, setBudget] = useState(null)
  const [error, setError] = useState(null)
  const [updated, setUpdated] = useState(null)
  const refresh = useCallback(async () => {
    try { setBudget(await otariApi.budget()); setUpdated(new Date()); setError(null) } catch (caught) { setError(caught) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  if (error) return <div className="planner-budget-inline unavailable"><span>AI PLANNER BUDGET</span><strong>Unavailable</strong><small>Otari status could not be read.</small></div>
  if (!budget) return <div className="planner-budget-inline"><span>AI PLANNER BUDGET</span><strong>Loading…</strong></div>
  const primary = budget.limits.find((limit) => limit.scope === 'api_token' && limit.limit_usd != null)
  const stale = budget.last_synced_at && Date.now() - new Date(budget.last_synced_at).getTime() > 90000
  return <div className={`planner-budget-inline ${budget.remaining_usd === 0 ? 'exhausted' : ''}`}><span>AI PLANNER BUDGET</span><strong>{money(budget.remaining_usd)} remaining</strong><small>{primary?.limit_usd != null ? `${money(primary.used_usd)} / ${money(primary.limit_usd)} used` : 'Live Otari data'} · {stale ? 'Stale cache' : `Updated ${updated?.toLocaleTimeString()}`}</small><button className="quiet" onClick={onViewUsage}>View usage</button></div>
}

export default function UsageScreen() {
  const [budget, setBudget] = useState(null)
  const [usage, setUsage] = useState(null)
  const [series, setSeries] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [bucket, setBucket] = useState('day')
  const [updated, setUpdated] = useState(null)

  const load = useCallback(async (manual = false) => {
    manual ? setRefreshing(true) : setLoading(true)
    try {
      const options = manual ? { query: '' } : {}
      const [nextBudget, nextUsage, nextSeries] = await Promise.all([otariApi.budget(options), otariApi.usage(options), otariApi.series(bucket, options)])
      setBudget(nextBudget); setUsage(nextUsage); setSeries(nextSeries); setUpdated(new Date()); setError(null)
    } catch (caught) { setError(caught) } finally { setLoading(false); setRefreshing(false) }
  }, [bucket])
  useEffect(() => { load() }, [load])

  const points = useMemo(() => series?.points || [], [series])
  return <main className="usage-shell">
    <section className="usage-hero"><div><p className="eyebrow">COST CONTROL / OTARI INTEGRATION</p><h1>Usage &amp; Budgets</h1><p>AI inference spending and budget controls, read directly from the planner credential.</p></div><button className="quiet" onClick={() => load(true)} disabled={loading || refreshing}>{refreshing ? 'Refreshing…' : 'Refresh live data'}</button></section>
    {error && <ErrorMessage error={error} />}
    {loading && !budget ? <section className="panel loading-panel">Loading live Otari budget and usage…</section> : budget && <><section className="usage-grid"><BudgetStatus budget={budget} /><article className="panel credential-card"><p className="eyebrow">CREDENTIAL</p><h2>agent-run</h2><dl><div><dt>Role</dt><dd>Planner</dd></div><div><dt>Provider</dt><dd>Otari</dd></div><div><dt>Routing policy</dt><dd>trustrail-planner</dd></div><div><dt>Last synced</dt><dd>{timestamp(updated)}</dd></div></dl></article></section>
      {usage && <section className="panel"><div className="panel-heading"><div><p className="eyebrow">USAGE SUMMARY</p><h2>Planner activity</h2></div><span className="muted">{timestamp(usage.start_date)} – {timestamp(usage.end_date)}</span></div><div className="usage-metrics">{[['SPEND', money(usage.totals.cost)], ['REQUESTS', usage.totals.request_count], ['INPUT TOKENS', usage.totals.prompt_tokens], ['OUTPUT TOKENS', usage.totals.completion_tokens], ['TOTAL TOKENS', usage.totals.total_tokens]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>{usage.by_model.length > 0 && <div className="table-wrap usage-models"><table><thead><tr><th>Model</th><th>Spend</th><th>Tokens</th><th>Requests</th></tr></thead><tbody>{usage.by_model.map((model, index) => <tr key={`${model.key || 'unknown'}-${index}`}><td>{model.label || model.key || 'Unknown model'}</td><td>{money(model.cost)}</td><td>{model.tokens.toLocaleString()}</td><td>{model.requests.toLocaleString()}</td></tr>)}</tbody></table></div>}</section>}
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">SPEND OVER TIME</p><h2>Usage series</h2></div><select className="usage-select" value={bucket} onChange={(event) => setBucket(event.target.value)}><option value="day">Daily</option><option value="hour">Hourly</option></select></div>{!points.length ? <p className="empty">No usage points returned for this period.</p> : <div className="spend-chart">{points.map((point) => <div className="chart-column" key={point.bucket_start}><div className="chart-bar" style={{ height: `${Math.max(4, (point.cost / Math.max(...points.map((item) => item.cost), 0.000001)) * 100)}%` }} title={`${money(point.cost)} · ${timestamp(point.bucket_start)}`} /><small>{new Date(point.bucket_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</small></div>)}</div>}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">APPLICABLE LIMITS</p><h2>Otari budget caps</h2></div><span className="muted">Live data</span></div><div className="table-wrap"><table><thead><tr><th>Scope</th><th>Spend limit</th><th>Used</th><th>Remaining</th><th>Reset</th></tr></thead><tbody>{budget.limits.map((limit, index) => <tr key={`${limit.scope}-${index}`}><td>{limit.scope}{limit.provider ? ` · ${limit.provider}` : ''}</td><td>{money(limit.limit_usd)}</td><td>{money(limit.used_usd)}</td><td>{money(limit.remaining_usd)}</td><td>{timestamp(limit.resets_at)}</td></tr>)}</tbody></table></div>{!budget.limits.length && <p className="empty">Otari reported no applicable limits.</p>}</section>
    </>}{budget && budget.last_synced_at && Date.now() - new Date(budget.last_synced_at).getTime() > 90000 && <div className="stale-note">Showing cached Otari data from {timestamp(budget.last_synced_at)}. Refresh to request live data.</div>}
  </main>
}
