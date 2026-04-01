/**
 * After `renderMarkdown` wraps list items, one logical ordered list broken by blank lines
 * becomes several `<ol>` segments (often one `<li>` each). Each new `<ol>` would restart
 * at 1 in the browser; this mutates `tokens` so continuation `<ol>`s get `start="N"`.
 *
 * Expects `tokens` from splitting HTML on full `<ol class="md-ol">…</ol>` chunks (regex
 * capture keeps delimiters in the array). Walks the array once:
 * - **Single-item `<ol>`**: part of a split list → increment `olCounter`, inject `start` from
 *   the second such block onward.
 * - **Multi-item `<ol>`**: a real list → reset `olCounter` / `inSequence` (native numbering OK).
 * - **Plain chunk while `inSequence`**: if it contains `<h2>`–`<h5>`, end the sequence
 *   (new section should not continue prior numbering).
 *
 * @param {string[]} tokens - split pieces; **mutated in place**
 */
function normalizeOrderedListSequence(tokens) {
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      // How many <li> in this block — 1 means markdown blank lines split one logical list into many <ol>s.
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        // First singleton keeps default start=1; later ones must continue the visible index (2, 3, …).
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        // Multi-item <ol>: browser counts 1..n correctly; clear continuation state.
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence) {
      // Between split lists: a heading starts a new section — stop continuing numbering across it.
      if (/<h[2-5]/.test(tokens[i])) {
        olCounter = 0
        inSequence = false
      }
    }
  }
}

export function escapeHtml(content) {
  if (!content) return ''
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function renderMarkdown(content) {
  if (!content) return ''
  
  // Remove leading h2 title (## xxx), since section title is already shown in outer layer
  let processedContent = escapeHtml(content.replace(/^##\s+.+\n+/, ''))
  
  // Process code blocks
  let html = processedContent.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre class="code-block" data-language="$1"><code>$2</code></pre>',
  )
  
  // Process inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  
  // Process headings
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  
  // Process blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')
  
  // Process lists - support nested lists
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (match, indent, num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })

  // Wrap unordered lists
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  // Wrap ordered lists
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')

  // Clean all whitespace between list items
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  // Clean whitespace after list opening tags
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  // Clean whitespace before list closing tags
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')
  
  // Process bold and italic (*** / ___ before ** and * so combined emphasis parses correctly)
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  
  // Process horizontal rules
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  
  // Process line breaks - blank lines become paragraph separators, single newlines become <br>
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  
  // Wrap in paragraphs
  html = '<p class="md-p">' + html + '</p>'
  
  // Clean empty paragraphs
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  // Clean <br> tags before and after block-level elements
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>)\s*<br>/g, '$1')
  // Clean <p><br> followed by block-level elements (caused by extra blank lines)
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr)/g, '$2')
  // Clean consecutive <br> tags
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  // Clean <br> between block-level elements and following paragraph tags
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>)<br>(<p|<div)/g, '$1$2')

  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  normalizeOrderedListSequence(tokens)
  html = tokens.join('')

  return html
}
