import { describe, it, expect, vi, beforeEach } from 'vitest'

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}))

vi.mock('./index', () => ({
  default: { post: postMock },
  requestWithRetry: (fn) => fn(),
}))

import { compareSimulations } from './simulation.js'

describe('compareSimulations', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('posts simulation_id_a and simulation_id_b to compare endpoint', async () => {
    postMock.mockResolvedValue({
      success: true,
      data: {
        simulation_a: { simulation: { simulation_id: 'sim_a' } },
        simulation_b: { simulation: { simulation_id: 'sim_b' } },
      },
    })

    const res = await compareSimulations({
      simulation_id_a: 'sim_a',
      simulation_id_b: 'sim_b',
    })

    expect(postMock).toHaveBeenCalledWith('/api/simulation/compare', {
      simulation_id_a: 'sim_a',
      simulation_id_b: 'sim_b',
    })
    expect(res.success).toBe(true)
    expect(res.data.simulation_a.simulation.simulation_id).toBe('sim_a')
  })
})
