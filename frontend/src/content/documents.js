import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: false })

export function readDocument(source) {
  const document = source.trimStart()
  const heading = /^# ([^\n]+)\r?\n?/.exec(document)
  const body = document.slice(heading?.[0].length ?? 0).trim()
  return {
    title: heading?.[1].trim(),
    summary: body.split(/\r?\n\s*\r?\n/, 1)[0],
    html: markdown.render(body),
  }
}
