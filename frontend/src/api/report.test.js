import { describe, it, expect, vi, beforeEach } from 'vitest'

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}))

vi.mock('./index', () => ({
  default: { post: postMock },
  requestWithRetry: (fn) => fn(),
}))

import { compareReports } from './report.js'

describe('compareReports', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('posts report_id_a and report_id_b to compare endpoint', async () => {
    postMock.mockResolvedValue({
      success: true,
      data: {
        report_a: { report_id: 'r1', markdown_content: '# A' },
        report_b: { report_id: 'r2', markdown_content: '# B' },
      },
    })

    const res = await compareReports({ report_id_a: 'r1', report_id_b: 'r2' })

    expect(postMock).toHaveBeenCalledWith('/api/report/compare', {
      report_id_a: 'r1',
      report_id_b: 'r2',
    })
    expect(res.success).toBe(true)
    expect(res.data.report_a.report_id).toBe('r1')
  })
})
