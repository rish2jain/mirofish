import { describe, it, expect } from 'vitest'
import { escapeHtml, renderMarkdown } from './markdown.js'

describe('markdown', () => {
  it('escapeHtml escapes HTML special chars', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;')
  })

  it('renderMarkdown wraps bold text', () => {
    const html = renderMarkdown('Hello **world**')
    expect(html).toContain('<strong>world</strong>')
  })

  it('renderMarkdown wraps bold+italic for *** and ___', () => {
    const a = renderMarkdown('Hello ***world***')
    expect(a).toContain('<strong><em>world</em></strong>')
    expect(a).not.toMatch(/\*<strong>/)
    const b = renderMarkdown('Hello ___world___')
    expect(b).toContain('<strong><em>world</em></strong>')
  })
})
