// Synthetic values used only by tests; never bundled into the dashboard.
const row = (date: string, value: number | null) => ({ date, value, realtime_start: '2024-03-01', realtime_end: '2024-03-01' })
export const fixture = {
  schema_version: 1, series_id: 'UNRATE', title: 'Unemployment Rate', source: 'FRED',
  source_url: 'https://fred.stlouisfed.org/series/UNRATE', units: 'Percent', frequency: 'Monthly',
  seasonal_adjustment: 'Seasonally Adjusted', retrieved_at: '2024-03-10T10:00:00+00:00',
  available_start: '2024-01-01', available_end: '2024-03-01',
  observations: [row('2024-01-01', 3.7), row('2024-02-01', null), row('2024-03-01', 3.8)],
}
