import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Library, Plus, Search, Trash2, Upload, X } from 'lucide-react'
import { api } from '../../api'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { Toggle } from '../../components/Fields'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { bookLine, entryHow, fileData, findEntries, LIBRARY_TYPES, WHEN_KINDS, type LibraryBook, type Lore, type LoreBook, type LoreEntry, type Passages, type WhenChoice, type WhenKind } from './loreText'

const LORE_KEY = ['lore']
const LIBRARY_KEY = ['library']

function useRun(): [string, (action: () => Promise<unknown>) => Promise<void>] {
  const [error, setError] = useState('')
  const run = async (action: () => Promise<unknown>) => {
    setError('')
    try { await action() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work. Try again.') }
  }
  return [error, run]
}

/** A button that picks a file and hands it on. */
function FilePick({ label, accept, busy, onFile }: { label: string; accept: string; busy: boolean; onFile: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null)
  return <>
    <input ref={input} type="file" accept={accept} hidden onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) onFile(file) }} />
    <button type="button" className="button" disabled={busy} onClick={() => input.current?.click()}><Upload aria-hidden="true" />{busy ? 'Reading…' : label}</button>
  </>
}

function DeleteBook({ name, onDelete }: { name: string; onDelete: () => Promise<void> }) {
  const [asking, setAsking] = useState(false)
  return <>
    <button type="button" className="text-button danger" onClick={() => setAsking(true)}><Trash2 aria-hidden="true" />Delete</button>
    {asking && <ConfirmDialog title={`Delete ${name}?`} onClose={() => setAsking(false)} actions={<>
      <button type="button" className="button" onClick={() => setAsking(false)}>Keep</button>
      <button type="button" className="button danger" onClick={() => void onDelete().then(() => setAsking(false))}>Delete</button>
    </>}><p>The story stops reading it. Import the file again to bring it back.</p></ConfirmDialog>}
  </>
}

/** Lorebooks (dungeon/lore.py): what the world knows as fact, entry by entry, and when each comes into the story. */
export function WorldLore() {
  const lore = useQuery({ queryKey: LORE_KEY, queryFn: () => api<Lore>('/lore') })
  const client = useQueryClient()
  const [error, run] = useRun()
  const [busy, setBusy] = useState(false)
  if (lore.isPending) return <Loading label="Loading lore" />
  if (lore.isError) return <ErrorNotice error={lore.error} />
  const store = (data: Lore) => client.setQueryData(LORE_KEY, data)
  const change = (path: string, body: unknown, method = 'PUT') => run(async () => store(await api<Lore>(path, body, method)))
  const bring = (file: File) => { setBusy(true); void run(async () => {
    await api(`/import/lorebook`, { filename: file.name, data: await fileData(file) })
    await client.invalidateQueries({ queryKey: LORE_KEY })
  }).finally(() => setBusy(false)) }
  return (
    <section className="world-lore" aria-labelledby="world-lore-heading">
      <h3 id="world-lore-heading"><BookOpen aria-hidden="true" />Lore</h3>
      <p className="subtle">What the world knows as fact. The narrator reads an entry when it is always on, when one of its keywords comes up in the last few lines, or when the scene fits its &ldquo;when&rdquo; (rain, night, a holiday, a place).</p>
      {!!lore.data.books.length && <ul className="city-list">
        {lore.data.books.map((book) => <LoreBookCard key={book.id} book={book} choices={lore.data.choices} change={change} />)}
      </ul>}
      <div className="form-actions"><FilePick label="Import a lorebook" accept=".json,.lorebook" busy={busy} onFile={bring} /></div>
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}

type Change = (path: string, body: unknown, method?: string) => Promise<void>

function LoreBookCard({ book, choices, change }: { book: LoreBook; choices: Lore['choices']; change: Change }) {
  const [query, setQuery] = useState('')
  const shown = findEntries(book.entries, query)
  return (
    <li className="city-card lore-book">
      <h4>{book.name}</h4>
      <p className="subtle">{bookLine(book)}{book.source_file ? ` · ${book.source_file}` : ''}</p>
      {book.description && <p>{book.description}</p>}
      <Toggle label="The story reads this book" checked={book.enabled} onChange={(enabled) => void change(`/lore/books/${book.id}`, { enabled })} />
      <details>
        <summary>Entries ({book.entries.length})</summary>
        {book.entries.length > 8 && <label className="search-field lore-search"><Search aria-hidden="true" />
          <span className="visually-hidden">Find an entry</span>
          <input type="search" placeholder="Find an entry" value={query} onChange={(event) => setQuery(event.target.value)} /></label>}
        <ul className="lore-entries">
          {shown.map((entry) => <LoreEntryRow key={entry.id} entry={entry} choices={choices} off={!book.enabled} change={change} />)}
        </ul>
        {!shown.length && <p className="subtle">No entry matches.</p>}
      </details>
      <div className="form-actions"><DeleteBook name={book.name} onDelete={() => change(`/lore/books/${book.id}`, undefined, 'DELETE')} /></div>
    </li>
  )
}

function LoreEntryRow({ entry, choices, off, change }: { entry: LoreEntry; choices: Lore['choices']; off: boolean; change: Change }) {
  const setWhen = (when: WhenChoice[]) => change(`/lore/entries/${entry.id}/when`, { when: when.map((item) => item.key) })
  return (
    <li className={entry.enabled && !off ? 'lore-entry' : 'lore-entry off'}>
      <EntryHead entry={entry} off={off} />
      <details><summary>Text</summary><p className="story-note">{entry.text}</p></details>
      <Toggle label="On" checked={entry.enabled} disabled={entry.pattern && !entry.enabled}
        hint={entry.pattern ? 'It finds its moment with a search pattern, which Dungeon does not run.' : undefined}
        onChange={(enabled) => void change(`/lore/entries/${entry.id}`, { enabled })} />
      {!entry.always && <WhenPicker when={entry.when} choices={choices} onSave={setWhen} />}
    </li>
  )
}

function EntryHead({ entry, off }: { entry: LoreEntry; off: boolean }) {
  return <>
    <div className="lore-entry-head">
      <strong>{entry.title || entry.keywords[0] || 'Untitled'}</strong>
      {entry.fits_now && !off && <span className="lore-now">Fits the scene now</span>}
    </div>
    <p className="subtle">{entryHow(entry)}{entry.when_guessed ? ' (read from its keywords)' : ''}</p>
  </>
}

/** The scene an entry fits besides its keywords: chips to take off, and a kind and a choice to add one. */
function WhenPicker({ when, choices, onSave }: { when: WhenChoice[]; choices: Lore['choices']; onSave: (when: WhenChoice[]) => Promise<void> }) {
  const [kind, setKind] = useState<WhenKind>('weather')
  const options = choices[kind].filter((choice) => !when.some((item) => item.key === choice.key))
  const [pick, setPick] = useState('')
  const add = () => { const choice = options.find((item) => item.key === pick) ?? options[0]; if (choice) void onSave([...when, choice]).then(() => setPick('')) }
  return (
    <div className="lore-when">
      {!!when.length && <ul className="lore-when-chips" aria-label="When it fits">
        {when.map((item) => <li key={item.key}>{item.label}
          <button type="button" className="icon-button" aria-label={`Take off ${item.label}`} onClick={() => void onSave(when.filter((one) => one.key !== item.key))}><X aria-hidden="true" /></button>
        </li>)}
      </ul>}
      <div className="lore-when-add">
        <select aria-label="Kind of moment" value={kind} onChange={(event) => { setKind(event.target.value as WhenKind); setPick('') }}>
          {WHEN_KINDS.filter(([key]) => choices[key].length).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
        <select aria-label="Moment" value={pick || options[0]?.key || ''} onChange={(event) => setPick(event.target.value)} disabled={!options.length}>
          {options.map((choice) => <option key={choice.key} value={choice.key}>{choice.label}</option>)}
        </select>
        <button type="button" className="text-button" onClick={add} disabled={!options.length}><Plus aria-hidden="true" />Add a when</button>
      </div>
    </div>
  )
}

/** The reference library (dungeon/library.py): long texts the narrator draws a few matching passages from each turn. */
export function WorldLibrary() {
  const library = useQuery({ queryKey: LIBRARY_KEY, queryFn: () => api<{ books: LibraryBook[] }>('/library') })
  const client = useQueryClient()
  const [error, run] = useRun()
  const [busy, setBusy] = useState(false)
  if (library.isPending) return <Loading label="Loading the library" />
  if (library.isError) return <ErrorNotice error={library.error} />
  const store = (data: { books: LibraryBook[] }) => client.setQueryData(LIBRARY_KEY, data)
  const change = (path: string, body: unknown, method = 'PUT') => run(async () => store(await api(path, body, method)))
  const add = (file: File) => { setBusy(true); void run(async () => {
    await api('/library/books', { filename: file.name, data: await fileData(file) })
    await client.invalidateQueries({ queryKey: LIBRARY_KEY })
  }).finally(() => setBusy(false)) }
  return (
    <section className="world-lore" aria-labelledby="world-library-heading">
      <h3 id="world-library-heading"><Library aria-hidden="true" />Reference library</h3>
      <p className="subtle">Long texts for the world: a world bible, a novel, a script, a wiki export. Each turn the narrator gets the few passages that match the last few lines. Nothing leaves this computer.</p>
      {!!library.data.books.length && <ul className="city-list">
        {library.data.books.map((book) => <li key={book.id} className="city-card">
          <h4>{book.name}</h4>
          <p className="subtle">{book.passages} passages{book.source_file ? ` · ${book.source_file}` : ''}</p>
          <Toggle label="The story reads this book" checked={book.enabled} onChange={(enabled) => void change(`/library/books/${book.id}`, { enabled })} />
          <LookInside book={book} />
          <div className="form-actions"><DeleteBook name={book.name} onDelete={() => change(`/library/books/${book.id}`, undefined, 'DELETE')} /></div>
        </li>)}
      </ul>}
      <div className="form-actions"><FilePick label="Add a book" accept={LIBRARY_TYPES} busy={busy} onFile={add} /></div>
      <p className="subtle">Text, Markdown, HTML, EPUB or a TiddlyWiki file.</p>
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}

/** A book's passages, so the player can see what the narrator would draw on: the first few, or the best matches. */
function LookInside({ book }: { book: LibraryBook }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [asked, setAsked] = useState('')
  const passages = useQuery({ queryKey: ['library-passages', book.id, asked], enabled: open,
    queryFn: () => api<Passages>(`/library/books/${book.id}/passages?q=${encodeURIComponent(asked)}`) })
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>Look inside</summary>
      <form className="lore-search-form" onSubmit={(event) => { event.preventDefault(); setAsked(query.trim()) }}>
        <label className="search-field"><Search aria-hidden="true" /><span className="visually-hidden">Find passages</span>
          <input type="search" placeholder="Find passages, as the narrator would" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <button type="submit" className="button">Find</button>
      </form>
      {passages.data && <ul className="lore-entries">
        {passages.data.passages.map((passage) => <li key={passage.id} className="lore-entry">
          {passage.title && <strong>{passage.title}</strong>}
          <p className="story-note">{passage.text}</p>
        </li>)}
      </ul>}
      {passages.data && !passages.data.passages.length && <p className="subtle">No passage matches.</p>}
    </details>
  )
}
