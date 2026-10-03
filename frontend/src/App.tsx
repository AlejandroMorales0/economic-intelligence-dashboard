import { useEffect, useMemo, useRef, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { filterRows, isDate, monthLabel, parseSeries, presetStart, views } from './series'
import type { ChartSeriesId, Series } from './series'
import { initialTheme, saveTheme } from './theme'

type LoadState = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; data: Series }

function useSavedSeries(indicator: ChartSeriesId, refresh: number): LoadState {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  useEffect(() => {
    const controller = new AbortController()
    let timedOut = false
    setState({ kind: 'loading' })
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort() }, 15000)
    async function load() {
      try {
        const response = await fetch(`/api/series/${indicator}`, { signal: controller.signal })
        if (!response.ok) {
          let message = 'Could not load saved data. Check that the local read API is running.'
          try {
            const body = await response.json()
            if (typeof body.error?.message === 'string') message = body.error.message
          } catch { /* A stopped proxy can return a non-JSON error. */ }
          throw new Error(message)
        }
        const data = parseSeries(await response.json(), indicator)
        if (!controller.signal.aborted) setState({ kind: 'ready', data })
      } catch (error) {
        if (!controller.signal.aborted || timedOut) setState({ kind: 'error', message: timedOut
          ? 'The request timed out. Check that the local read API is running.'
          : error instanceof Error ? error.message : 'Unable to load saved data.' })
      } finally { window.clearTimeout(timeout) }
    }
    void load()
    return () => { controller.abort(); window.clearTimeout(timeout) }
  }, [refresh, indicator])
  return state
}

export default function App() {
  const [refresh, setRefresh] = useState({ UNRATE: 0, CPIAUCSL_YOY: 0 })
  const states = { UNRATE: useSavedSeries('UNRATE', refresh.UNRATE), CPIAUCSL_YOY: useSavedSeries('CPIAUCSL_YOY', refresh.CPIAUCSL_YOY) }
  const [indicator, setIndicator] = useState<ChartSeriesId | null>(null)
  const [theme, setTheme] = useState(initialTheme)
  const view = indicator ? views[indicator] : null
  const state = indicator ? states[indicator] : null
  const titleRef = useRef<HTMLHeadingElement>(null)
  const previousIndicator = useRef<ChartSeriesId | null>(null)

  useEffect(() => {
    if (indicator && previousIndicator.current === null) titleRef.current?.focus()
    else if (!indicator && previousIndicator.current) document.getElementById(`open-${previousIndicator.current}`)?.focus()
    previousIndicator.current = indicator
  }, [indicator])

  function reload() {
    setRefresh(current => indicator ? { ...current, [indicator]: current[indicator] + 1 }
      : { UNRATE: current.UNRATE + 1, CPIAUCSL_YOY: current.CPIAUCSL_YOY + 1 })
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#0b1020' : '#f5f6ff')
  }, [theme])

  function toggleTheme() {
    const next = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    saveTheme(next)
  }

  function selectIndicator(id: ChartSeriesId) {
    setIndicator(id)
  }

  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="header-inner flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="brand-mark" aria-hidden="true"><span /><span /><span /><span /></div>
            <div><h1>U.S. Economic Intelligence Dashboard</h1><p>National economic data</p></div>
          </div>
          <div className="header-actions flex items-center gap-3">
            <span className="scope-badge"><span /> United States</span>
            <button className="theme-toggle" aria-label="Toggle dark mode" aria-pressed={theme === 'dark'}
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} onClick={toggleTheme}>
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                {theme === 'light' ? <path d="M20.8 13A9 9 0 0 1 11 3.2 9 9 0 1 0 20.8 13Z" />
                  : <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>}
              </svg>
              {theme === 'light' ? 'Dark mode' : 'Light mode'}
            </button>
          </div>
        </div>
      </header>
      <main className="page-content">
        {indicator && <div className="detail-navigation flex flex-wrap items-center gap-5">
          <button className="back-button" onClick={() => setIndicator(null)}>← Back to overview</button>
          <div className="indicator-nav flex gap-2" role="tablist" aria-label="Economic domain">
            {(['UNRATE', 'CPIAUCSL_YOY'] as const).map(id => <button key={id} role="tab" id={`tab-${id}`}
              aria-selected={indicator === id} aria-controls="indicator-panel" tabIndex={indicator === id ? 0 : -1}
              onClick={() => selectIndicator(id)} onKeyDown={event => {
                if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
                event.preventDefault()
                const next = event.key === 'Home' ? 'UNRATE' : event.key === 'End' ? 'CPIAUCSL_YOY'
                  : id === 'UNRATE' ? 'CPIAUCSL_YOY' : 'UNRATE'
                selectIndicator(next)
                document.getElementById(`tab-${next}`)?.focus()
              }}>{id === 'UNRATE' ? 'Labor' : 'Inflation'}</button>)}
          </div>
        </div>}
        <div id="indicator-panel" role={indicator ? 'tabpanel' : undefined} aria-labelledby={indicator ? `tab-${indicator}` : undefined}>
          <div className="section-intro flex flex-wrap items-end justify-between gap-4">
            <div><p className="eyebrow">{view?.domain ?? 'National economic data'}</p>
              <h2 ref={titleRef} tabIndex={-1}>{view?.title ?? 'Economic overview'}</h2>
              {!indicator && <p className="overview-subtitle">Explore an indicator to see its full history and details.</p>}
            </div>
            <button className="secondary-button" disabled={indicator ? state?.kind === 'loading' : Object.values(states).every(item => item.kind === 'loading')} onClick={reload}>
              Reload saved data
            </button>
          </div>
          {!indicator ? <div className="overview-grid">
            {(['UNRATE', 'CPIAUCSL_YOY'] as const).map(id => <IndicatorTile key={id} indicator={id} state={states[id]} onOpen={() => selectIndicator(id)} />)}
          </div> : <>
            {state?.kind === 'loading' && <div className="state-panel" role="status"><span className="loading-dot" />Loading {view?.loading} data…</div>}
            {state?.kind === 'error' && <div className="state-panel error-panel" role="alert">
              <h3>Data unavailable</h3><p>{state.message}</p>
              <button className="primary-button" onClick={reload}>Try again</button>
            </div>}
            {state?.kind === 'ready' && <IndicatorView key={state.data.series_id} data={state.data} indicator={indicator} />}
          </>}
        </div>
        <footer className="page-footer flex flex-wrap justify-between gap-3">
          <span>U.S. Economic Intelligence Dashboard</span><span>National scope · {view?.domain ?? 'Overview'}</span>
        </footer>
      </main>
    </div>
  )
}

function IndicatorTile({ indicator, state, onOpen }: { indicator: ChartSeriesId; state: LoadState; onOpen: () => void }) {
  const view = views[indicator]
  const inflation = indicator === 'CPIAUCSL_YOY'
  const data = state.kind === 'ready' ? state.data : null
  const latest = data?.observations.filter(row => row.value !== null).at(-1)
  const recent = data ? filterRows(data.observations, data.available_end ? presetStart(data.available_end, 5) : '', '') : []
  const numeric = recent.filter(row => row.value !== null)
  const chartRows = recent.map(row => ({ ...row, timestamp: Date.parse(`${row.date}T00:00:00Z`) }))
  return (
    <article className="overview-tile" data-domain={inflation ? 'inflation' : 'labor'} aria-labelledby={`tile-title-${indicator}`}>
      <div className="tile-header flex items-start justify-between gap-4">
        <div><p className="eyebrow">{view.domain}</p><h3 id={`tile-title-${indicator}`}>{view.title}</h3></div>
        <span className="tile-expand" aria-hidden="true">↗</span>
      </div>
      {state.kind === 'loading' && <div className="tile-state" role="status">Loading {view.loading} data…</div>}
      {state.kind === 'error' && <div className="tile-state" role="alert"><strong>Data unavailable</strong><p>{state.message}</p><span>Open details to retry</span></div>}
      {data && <>
        <div className="tile-value-row flex flex-wrap items-baseline gap-3" id={`tile-summary-${indicator}`}>
          <p className="tile-value">{latest ? `${latest.value!.toFixed(1)}%` : '—'}</p>
          <p className="metric-detail">{latest ? `Latest · ${monthLabel(latest.date)}` : 'No numeric observations'}</p>
        </div>
        <p className="tile-units">{inflation ? 'Year-over-year change · seasonally adjusted CPI input' : 'Monthly · percent · seasonally adjusted'}</p>
        {numeric.length ? <div className="tile-chart" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <LineChart data={chartRows} accessibilityLayer={false} margin={{ top: 12, right: 14, bottom: 5, left: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 5" />
              <XAxis dataKey="timestamp" type="number" domain={['dataMin', 'dataMax']} scale="time" tickCount={4}
                tickFormatter={value => new Date(value).getUTCFullYear().toString()} axisLine={false} tickLine={false}
                tick={{ fill: 'var(--muted)', fontSize: 11 }} minTickGap={38} />
              <YAxis width={42} domain={[inflation ? (minimum: number) => Math.min(0, Math.floor(minimum)) : 0, 'auto']}
                tickFormatter={value => `${value}%`} axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
              {inflation && <ReferenceLine y={0} stroke="var(--muted)" />}
              <Line dataKey="value" type="linear" stroke="var(--chart-series)" strokeWidth={2.5} dot={numeric.length <= 24}
                activeDot={false} connectNulls={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div> : <div className="tile-state">No numeric observations to plot.</div>}
        <div className="tile-meta flex flex-wrap justify-between gap-2">
          <span>{recent.length ? `${monthLabel(recent[0].date)} – ${monthLabel(recent.at(-1)!.date)}` : 'No available history'}</span>
          <span>FRED · {view.sourceId}</span>
        </div>
        <p className="tile-freshness">Retrieved {new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(data.retrieved_at))} · Missing values remain gaps</p>
      </>}
      <div className="tile-footer">View full chart <span aria-hidden="true">→</span></div>
      <button id={`open-${indicator}`} className="tile-open" aria-label={`Open ${view.title}`}
        aria-describedby={data ? `tile-summary-${indicator}` : undefined} onClick={onOpen} />
    </article>
  )
}

function IndicatorView({ data, indicator }: { data: Series; indicator: ChartSeriesId }) {
  const view = views[indicator]
  const inflation = indicator === 'CPIAUCSL_YOY'
  const [start, setStart] = useState(data.available_start ?? '')
  const [end, setEnd] = useState(data.available_end ?? '')
  const [preset, setPreset] = useState('All')
  const validRange = (!start || isDate(start)) && (!end || isDate(end)) && (!start || !end || start <= end)
  const rows = useMemo(() => validRange ? filterRows(data.observations, start, end) : [], [data, start, end, validRange])
  const numeric = rows.filter(row => row.value !== null)
  const latest = numeric.at(-1)
  const chartRows = rows.map(row => ({ ...row, timestamp: Date.parse(`${row.date}T00:00:00Z`) }))
  const retrieved = new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
  }).format(new Date(data.retrieved_at))

  function selectPreset(label: string, years?: number) {
    setPreset(label)
    setStart(years && data.available_end ? presetStart(data.available_end, years) : data.available_start ?? '')
    setEnd(data.available_end ?? '')
  }

  return (
    <div className="indicator-view" data-domain={inflation ? 'inflation' : 'labor'}>
      <div className="summary-grid grid gap-5 md:grid-cols-3">
        <section className="metric-card primary-metric">
          <h3>Latest rate in selected range</h3>
          <p className="metric-value">{latest ? `${latest.value!.toFixed(1)}%` : '—'}</p>
          <p className="metric-detail">{latest ? monthLabel(latest.date) : 'No numeric observations'}</p>
        </section>
        <section className="metric-card">
          <h3>Selected observations</h3><p className="metric-value">{rows.length.toLocaleString()}</p>
          <p className="metric-detail">{rows.length ? `${monthLabel(rows[0].date)} – ${monthLabel(rows.at(-1)!.date)}` : 'No observations in range'}
            {rows.length > numeric.length && <span className="block">{rows.length - numeric.length} missing {rows.length - numeric.length === 1 ? 'value' : 'values'}</span>}
          </p>
        </section>
        <section className="metric-card freshness-card">
          <h3>Data retrieved</h3><p className="retrieval-date">{retrieved}</p>
          <p className="metric-detail">{data.available_end ? `Available through ${monthLabel(data.available_end)}` : 'No available observations'}</p>
        </section>
      </div>

      <section className="chart-panel" aria-labelledby="chart-title">
        <div className="chart-header flex flex-wrap items-start justify-between gap-5">
          <div><h3 id="chart-title">{view.chartTitle}</h3><p>{data.frequency} · {data.units} · {inflation ? 'Seasonally adjusted CPI input' : data.seasonal_adjustment}</p></div>
          <div className="preset-group flex" role="group" aria-label="Date range presets">
            {['1Y', '5Y', '10Y', 'All'].map((label, index) => <button key={label} aria-pressed={preset === label}
              onClick={() => selectPreset(label, [1, 5, 10][index])}>{label}</button>)}
          </div>
        </div>
        {inflation && <div className="method-note">
          <p><strong>Year-over-year change:</strong> (CPI this month / CPI in the same month one year earlier − 1) × 100.</p>
          <p>Calculated from seasonally adjusted CPIAUCSL. This can differ from the commonly reported inflation rate based on unadjusted CPI. Missing current or comparison months produce gaps.</p>
        </div>}
        <div className="date-controls flex flex-wrap items-end gap-4">
          <label>Start date<input type="date" value={start} aria-describedby={!validRange ? 'range-error' : undefined}
            onChange={event => { setStart(event.target.value); setPreset('Custom') }} /></label>
          <label>End date<input type="date" value={end} aria-describedby={!validRange ? 'range-error' : undefined}
            onChange={event => { setEnd(event.target.value); setPreset('Custom') }} /></label>
          <button className="text-button" onClick={() => selectPreset('All')}>Reset range</button>
        </div>
        {!validRange ? <div className="chart-empty" role="alert" id="range-error">Enter valid dates with the start on or before the end.</div>
          : !numeric.length ? <div className="chart-empty" role="status"><h4>No data to plot</h4><p>{rows.length
              ? 'All observations in this range have missing values.' : 'Choose another date range or ingest more history.'}</p></div>
          : <div className="chart-area" role="img" aria-label={`${view.label} chart with ${numeric.length} numeric observations, ${monthLabel(rows[0].date)} to ${monthLabel(rows.at(-1)!.date)}. Exact values available in the observation table below.`}>
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <LineChart data={chartRows} margin={{ top: 20, right: 20, bottom: 12, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="timestamp" type="number" domain={['dataMin', 'dataMax']} scale="time"
                    tickFormatter={value => new Intl.DateTimeFormat('en-US', { year: 'numeric', month: rows.length <= 24 ? 'short' : undefined, timeZone: 'UTC' }).format(new Date(value))}
                    tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} minTickGap={48} />
                  <YAxis domain={[inflation ? (minimum: number) => Math.min(0, Math.floor(minimum)) : 0, 'auto']} tickFormatter={value => `${value}%`} tick={{ fill: 'var(--muted)', fontSize: 12 }}
                    axisLine={false} tickLine={false} width={52} />
                  <Tooltip labelFormatter={value => monthLabel(new Date(Number(value)).toISOString().slice(0, 10))}
                    formatter={value => [`${Number(value).toFixed(1)}%`, view.label]}
                    contentStyle={{ borderRadius: 12, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: 13, boxShadow: 'var(--shadow)' }}
                    labelStyle={{ color: 'var(--text)' }} itemStyle={{ color: 'var(--chart-series)' }}
                    cursor={{ stroke: 'var(--muted)', strokeDasharray: '3 4' }} />
                  {inflation && <ReferenceLine y={0} stroke="var(--muted)" />}
                  <Line dataKey="value" name={view.label} type="linear" stroke="var(--chart-series)" strokeWidth={2.5}
                    dot={numeric.length <= 24 ? { r: 3, fill: 'var(--chart-series)', strokeWidth: 0 } : false}
                    activeDot={{ r: 5 }} connectNulls={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>}
        <div className="chart-caption flex flex-wrap justify-between gap-3">
          <span><span className="legend-line" />{inflation ? 'CPIAUCSL · Year-over-year change' : 'UNRATE · Unemployment rate'}</span>
          <span>Missing values appear as gaps</span>
        </div>
      </section>

      <div className="source-note flex flex-wrap justify-between gap-3">
        <p>Source: <a href={data.source_url} target="_blank" rel="noreferrer">FRED · {view.sourceId} ↗</a> · U.S. Bureau of Labor Statistics</p>
        <p>Observation dates identify months; retrieval time records the saved snapshot.</p>
      </div>
      <details className="observations-panel">
        <summary>View selected observations <span>({rows.length})</span></summary>
        <div className="table-scroll">
          <table><caption className="sr-only">{view.label} observations in the selected date range</caption>
            <thead><tr><th scope="col">Month</th><th scope="col">{view.label}</th></tr></thead>
            <tbody>{[...rows].reverse().map(row => <tr key={row.date}><th scope="row">{monthLabel(row.date)}</th>
              <td>{row.value === null ? 'Missing' : `${row.value.toFixed(1)}%`}</td></tr>)}</tbody>
          </table>
          {!rows.length && <p className="table-empty">No observations in the selected range.</p>}
        </div>
      </details>
    </div>
  )
}
