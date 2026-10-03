import { describe, expect, it } from 'vitest'
import { filterRows, isDate, monthLabel, parseSeries, presetStart } from './series'

import { fixture, inflationFixture } from './test-fixtures'

describe('series contract and date calculations', () => {
  it('accepts derived inflation including deflation and checks lineage', () => {
    expect(parseSeries(inflationFixture, 'CPIAUCSL_YOY').observations[2].value).toBe(-2)
    expect(() => parseSeries(inflationFixture)).toThrow()
    expect(() => parseSeries({ ...inflationFixture, transformation: undefined }, 'CPIAUCSL_YOY')).toThrow()
    expect(() => parseSeries({ ...inflationFixture, observations: [{ ...inflationFixture.observations[0], value: -100 }] }, 'CPIAUCSL_YOY')).toThrow()
  })
  it('validates the contract and preserves missing values', () => {
    expect(parseSeries(fixture).observations[1].value).toBeNull()
    expect(() => parseSeries({ ...fixture, observations: [{ ...fixture.observations[0], value: NaN }] })).toThrow()
    expect(() => parseSeries({ ...fixture, observations: [...fixture.observations].reverse() })).toThrow()
    expect(() => parseSeries({ ...fixture, units: 'Dollars' })).toThrow()
  })
  it('filters inclusive bounds without converting nulls to zero', () => {
    expect(filterRows(fixture.observations, '2024-02-01', '2024-03-01')).toEqual(fixture.observations.slice(1))
    expect(filterRows(fixture.observations, '2025-01-01', '')).toEqual([])
    expect(filterRows(fixture.observations, '', '')).toHaveLength(3)
  })
  it('anchors presets to available data and includes exactly 12 months for 1Y', () => {
    expect(presetStart('2026-08-01', 1)).toBe('2025-09-01')
    expect(presetStart('2026-12-01', 5)).toBe('2022-01-01')
  })
  it('formats month dates without local timezone shifts', () => {
    expect(monthLabel('2024-01-01')).toBe('Jan 2024')
    expect(isDate('2024-02-30')).toBe(false)
    expect(isDate('2024-02-29')).toBe(true)
  })
})
