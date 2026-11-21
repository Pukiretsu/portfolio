import { readDocument } from './documents'

const sources = import.meta.glob('./projects/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const documents = Object.fromEntries(
  Object.entries(sources).map(([path, source]) => [path, readDocument(source)]),
)
const slugs = Object.keys(documents)
  .map(path => /^\.\/projects\/([a-z0-9-]+)\.md$/.exec(path)?.[1])
  .filter(Boolean)

export function projectPosts(locale) {
  return slugs.map(slug => {
    const base = `./projects/${slug}`
    const translation = documents[`${base}.${locale}.md`]
    const document = translation ?? documents[`${base}.md`]
    return { ...document, slug, language: translation ? locale : 'en', title: document.title || slug.replaceAll('-', ' ') }
  }).sort((a, b) => a.title.localeCompare(b.title, locale))
}
