/** Lorebooks (dungeon/lore.py) and the reference library (dungeon/library.py), as the Worlds page shows them. */

export interface WhenChoice { key: string; label: string }
export interface LoreEntry {
  id: string; title: string; text: string; keywords: string[]; always: boolean; pattern: boolean; enabled: boolean
  /** The scene this entry fits besides its keywords; `when_guessed` when the app read it from the keywords. */
  when: WhenChoice[]; when_guessed: boolean; fits_now: boolean
}
export interface LoreBook { id: string; name: string; description: string; source_format: string; source_file: string; city_id: string | null; enabled: boolean; entries: LoreEntry[] }
export type WhenKind = 'weather' | 'season' | 'time' | 'day' | 'holiday' | 'place'
export interface Lore { books: LoreBook[]; choices: Record<WhenKind, WhenChoice[]> }

export interface LibraryBook { id: string; name: string; source_format: string; source_file: string; enabled: boolean; passages: number }
export interface Passages { total: number; passages: { id: string; title: string; text: string }[] }

export const WHEN_KINDS: [WhenKind, string][] = [['weather', 'Weather'], ['season', 'Season'], ['time', 'Time of day'], ['day', 'Day'], ['holiday', 'Holiday'], ['place', 'Place']]
export const LIBRARY_TYPES = '.txt,.md,.markdown,.html,.htm,.xhtml,.epub'

/** "12 entries · 3 off · always on: 2". */
export function bookLine(book: LoreBook): string {
  const off = book.entries.filter((entry) => !entry.enabled).length
  const always = book.entries.filter((entry) => entry.always).length
  const count = book.entries.length === 1 ? '1 entry' : `${book.entries.length} entries`
  return [count, off ? `${off} off` : '', always ? `${always} always on` : '', book.city_id ? 'from a city map' : ''].filter(Boolean).join(' · ')
}

/** How an entry comes into the story, in words. */
export function entryHow(entry: LoreEntry): string {
  if (entry.always) return 'Always in the story'
  const words = entry.keywords.length ? `When someone says ${entry.keywords.slice(0, 4).join(', ')}${entry.keywords.length > 4 ? '…' : ''}` : ''
  const when = entry.when.length ? `${words ? 'or when' : 'When'} the scene fits: ${entry.when.map((item) => item.label).join(', ')}` : ''
  return [words, when].filter(Boolean).join(', ') || 'Never on its own'
}

/** Lore entries matching a search, in their titles, keywords or text. */
export function findEntries(entries: LoreEntry[], query: string): LoreEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return entries
  return entries.filter((entry) => {
    const hay = `${entry.title} ${entry.keywords.join(' ')} ${entry.text}`.toLowerCase()
    return words.every((word) => hay.includes(word))
  })
}

/** A file as base64, for the import routes. */
export async function fileData(file: Blob): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let text = ''
  for (let start = 0; start < bytes.length; start += 0x8000) text += String.fromCharCode(...bytes.subarray(start, start + 0x8000))
  return btoa(text)
}
