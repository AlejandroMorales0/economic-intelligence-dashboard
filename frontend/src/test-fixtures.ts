// Synthetic values used only by tests; never bundled into the dashboard.
const row = (date: string, value: number | null) => ({ date, value, realtime_start: '2024-03-01', realtime_end: '2024-03-01' })
export const fixture = {
  schema_version: 1, series_id: 'UNRATE', title: 'Unemployment Rate', source: 'FRED',
  source_url: 'https://fred.stlouisfed.org/series/UNRATE', units: 'Percent', frequency: 'Monthly',
  seasonal_adjustment: 'Seasonally Adjusted', retrieved_at: '2024-03-10T10:00:00+00:00',
  available_start: '2024-01-01', available_end: '2024-03-01',
  observations: [row('2024-01-01', 3.7), row('2024-02-01', null), row('2024-03-01', 3.8)],
}

export const inflationFixture = {
  ...fixture, series_id: 'CPIAUCSL_YOY', title: 'CPI inflation, year over year',
  source_url: 'https://fred.stlouisfed.org/series/CPIAUCSL', source_series_id: 'CPIAUCSL',
  transformation: { kind: 'year_over_year', lag_months: 12,
    formula: '(CPI this month / CPI in the same month one year earlier - 1) * 100' },
  observations: [row('2024-01-01', 5), row('2024-02-01', null), row('2024-03-01', -2)],
}
