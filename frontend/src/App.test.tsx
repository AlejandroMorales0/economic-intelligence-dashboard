import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { fixture, inflationFixture } from './test-fixtures'

// Layout is verified separately in a real browser. jsdom has no chart dimensions.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: () => <div data-testid="chart" />, CartesianGrid: () => null,
  Line: () => null, ReferenceLine: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}))

function respond(data: unknown = fixture, ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok, json: async () => data }))
}

describe('dashboard', () => {
  it('shows loading before data arrives', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading unemployment data')
  })
  it('loads the saved series and filters cards and table together', async () => {
    respond()
    render(<App />)
    await screen.findByText('Latest rate in selected range')
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2024-01-01' } })
    expect(screen.getByText('Latest rate in selected range').parentElement).toHaveTextContent('3.7%')
    expect(screen.getByText('Selected observations').parentElement).toHaveTextContent('1')
    fireEvent.click(screen.getByText(/View selected observations/))
    expect(screen.getAllByRole('row')).toHaveLength(2)
    fireEvent.click(screen.getByText('Reset range'))
    expect(screen.getAllByRole('row')).toHaveLength(4)
    expect(screen.getByRole('link', { name: /FRED/ })).toHaveAttribute('href', fixture.source_url)
  })
  it('shows empty, all-missing, and invalid range states', async () => {
    respond(); render(<App />); await screen.findByText('Latest rate in selected range')
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2025-12-31' } })
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2025-01-01' } })
    expect(screen.getByText('No data to plot')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2024-02-01' } })
    expect(screen.getByRole('alert')).toHaveTextContent('start on or before the end')
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2024-02-01' } })
    expect(screen.getByText('All observations in this range have missing values.')).toBeInTheDocument()
  })
  it('reports API errors and retries successfully', async () => {
    respond({ error: { message: 'No saved UNRATE data. Run ingest-unrate first.' } }, false)
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Run ingest-unrate first')
    respond()
    fireEvent.click(screen.getByText('Try again'))
    await waitFor(() => expect(screen.getByTestId('chart')).toBeInTheDocument())
  })
  it('switches domains, displays deflation and methodology, and resets filters on return', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => ({
      ok: true, json: async () => url.endsWith('CPIAUCSL_YOY') ? inflationFixture : fixture,
    })))
    render(<App />)
    await screen.findByText('Latest rate in selected range')
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2024-01-01' } })
    fireEvent.click(screen.getByRole('tab', { name: 'Inflation' }))
    await screen.findByText('Year-over-year change:')
    expect(screen.getByText('Latest rate in selected range').parentElement).toHaveTextContent('-2.0%')
    expect(screen.getByRole('link', { name: /FRED/ })).toHaveAttribute('href', inflationFixture.source_url)
    expect(screen.getByLabelText('End date')).toHaveValue('2024-03-01')
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2024-01-01' } })
    expect(screen.getByText('Latest rate in selected range').parentElement).toHaveTextContent('5.0%')
    fireEvent.click(screen.getByRole('tab', { name: 'Labor' }))
    await screen.findByRole('heading', { name: 'Unemployment over time' })
    expect(screen.getByText('Latest rate in selected range').parentElement).toHaveTextContent('3.8%')
  })
  it('shows a CPI ingestion hint when inflation data is missing', async () => {
    respond(); render(<App />); await screen.findByText('Latest rate in selected range')
    respond({ error: { message: 'No saved CPIAUCSL data. Run ingest-cpi first.' } }, false)
    fireEvent.click(screen.getByRole('tab', { name: 'Inflation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Run ingest-cpi first')
  })
  it('supports keyboard domain navigation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => ({
      ok: true, json: async () => url.endsWith('CPIAUCSL_YOY') ? inflationFixture : fixture,
    })))
    render(<App />); await screen.findByText('Latest rate in selected range')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Labor' }), { key: 'ArrowRight' })
    await screen.findByText('Year-over-year change:')
    expect(screen.getByRole('tab', { name: 'Inflation' })).toHaveFocus()
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Inflation' }), { key: 'Home' })
    await screen.findByRole('heading', { name: 'Unemployment over time' })
    expect(screen.getByRole('tab', { name: 'Labor' })).toHaveAttribute('aria-selected', 'true')
  })
})
