export type Observation = {
  date: string
  value: number | null
  realtime_start: string | null
  realtime_end: string | null
}

export type Series = {
  schema_version: number
  series_id: string
  title: string
  source: string
  source_url: string
  units: string
  frequency: string
  seasonal_adjustment: string
  retrieved_at: string
  available_start: string | null
  available_end: string | null
  observations: Observation[]
  source_series_id?: string
  transformation?: { kind: string; lag_months: number; formula: string }
}

export const views = {
  UNRATE: { domain: 'Labor market', title: 'Unemployment rate', chartTitle: 'Unemployment over time',
    label: 'Unemployment rate', loading: 'unemployment', sourceId: 'UNRATE' },
  CPIAUCSL_YOY: { domain: 'Inflation', title: 'CPI inflation, year over year', chartTitle: 'Inflation over time',
    label: 'Inflation (YoY)', loading: 'inflation', sourceId: 'CPIAUCSL' },
} as const
export type ChartSeriesId = keyof typeof views

export function isDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value
}

export function parseSeries(value: unknown, expectedId: ChartSeriesId = 'UNRATE'): Series {
  const data = value as Series | null
  if (!data || data.schema_version !== 1 || data.series_id !== expectedId ||
      data.units !== 'Percent' || data.frequency !== 'Monthly' ||
      data.source !== 'FRED' || data.source_url !== `https://fred.stlouisfed.org/series/${views[expectedId].sourceId}` ||
      typeof data.title !== 'string' || typeof data.seasonal_adjustment !== 'string' ||
      typeof data.retrieved_at !== 'string' || !Number.isFinite(Date.parse(data.retrieved_at)) ||
      !Array.isArray(data.observations)) throw new Error('The saved series has an unexpected format. Run ingestion again.')
  if (expectedId === 'CPIAUCSL_YOY' && (data.source_series_id !== 'CPIAUCSL' ||
      data.transformation?.kind !== 'year_over_year' || data.transformation.lag_months !== 12 ||
      data.transformation.formula !== '(CPI this month / CPI in the same month one year earlier - 1) * 100')) {
    throw new Error('The inflation calculation metadata is invalid. Run ingestion again.')
  }
  let previous = ''
  for (const row of data.observations) {
    if (!row || typeof row.date !== 'string' || !isDate(row.date) || row.date <= previous ||
        !(row.value === null || (typeof row.value === 'number' && Number.isFinite(row.value) &&
          (expectedId === 'UNRATE' ? row.value >= 0 && row.value <= 100 : row.value > -100)))) {
      throw new Error('The saved observations are invalid. Run ingestion again.')
    }
    previous = row.date
  }
  if (data.available_start !== (data.observations[0]?.date ?? null) ||
      data.available_end !== (data.observations.at(-1)?.date ?? null)) {
    throw new Error('The saved series coverage is inconsistent. Run ingestion again.')
  }
  return data
}

export function filterRows(rows: Observation[], start: string, end: string): Observation[] {
  return rows.filter(row => (!start || row.date >= start) && (!end || row.date <= end))
}

export function presetStart(end: string, years: number): string {
  const date = new Date(`${end}T00:00:00Z`)
  date.setUTCFullYear(date.getUTCFullYear() - years)
  date.setUTCMonth(date.getUTCMonth() + 1, 1)
  return date.toISOString().slice(0, 10)
}

export function monthLabel(date: string): string {
  return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${date}T00:00:00Z`))
}
