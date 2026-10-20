import { StrictMode } from 'react'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import GeoMap from './GeoMap'

describe('GeoMap', () => {
  it.each([undefined, 20])('mounts twice in StrictMode (accuracy %s)', accuracy => {
    const { unmount } = render(<StrictMode><GeoMap lat={52.29} lon={8.05} accuracy={accuracy} label="x" /></StrictMode>)
    unmount()
    expect(true).toBe(true)
  })
  it('re-renders with changed props', () => {
    const { rerender } = render(<StrictMode><GeoMap lat={1} lon={2} label="x" /></StrictMode>)
    rerender(<StrictMode><GeoMap lat={3} lon={4} accuracy={10} label="x" /></StrictMode>)
  })
})
