import { readDocument } from './documents'

const sources = import.meta.glob('./projects/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

export const posts = Object.entries(sources).map(([path, source]) => {
  const slug = path.slice('./projects/'.length, -'.md'.length)
  const document = readDocument(source)
  return { ...document, slug, title: document.title || slug.replaceAll('-', ' ') }
}).sort((a, b) => a.title.localeCompare(b.title))
