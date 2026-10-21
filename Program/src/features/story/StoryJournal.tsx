import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Journal, JournalEntry, JournalQuest } from '../../types'
import { Notice } from '../../components/Feedback'
import { journalKind, questState } from './storyText'

const JOURNAL_KEY = ['story-journal']

/** What your character knows (dungeon/ledger.py): facts the game keeps, which you can correct or add to. */
export function StoryJournal() {
  const client = useQueryClient()
  const journal = useQuery({ queryKey: JOURNAL_KEY, queryFn: () => api<Journal>('/story/journal') })
  const [error, setError] = useState('')
  const change = async (request: () => Promise<Journal>) => {
    setError('')
    try { client.setQueryData(JOURNAL_KEY, await request()) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  if (!journal.data) return null
  const { entries, quests } = journal.data
  return (
    <details className="story-people">
      <summary>What you know ({entries.length})</summary>
      {!!quests.length && <Underway quests={quests} />}
      <ul>
        {entries.map((entry) => <JournalLine key={entry.id} entry={entry}
          onSave={(text) => change(() => api<Journal>(`/story/journal/${entry.id}`, { text }, 'PATCH'))}
          onRemove={() => void change(() => api<Journal>(`/story/journal/${entry.id}`, undefined, 'DELETE'))} />)}
      </ul>
      <AddNote onAdd={(subject, text) => change(() => api<Journal>('/story/journal', { subject, text }))} />
      {error && <Notice tone="error">{error}</Notice>}
    </details>
  )
}

/** The quests your character knows of (dungeon/quests.py), with the story time left. */
function Underway({ quests }: { quests: JournalQuest[] }) {
  return (
    <ul aria-label="Underway">
      {quests.map((quest) => <li key={quest.id}>
        <p className="subtle">{questState(quest)}</p>
        <p><strong>{quest.title}</strong></p>
        <p>{quest.status === 'open' ? quest.hook : quest.outcome}</p>
      </li>)}
    </ul>
  )
}

interface LineProps { entry: JournalEntry; onSave: (text: string) => Promise<void>; onRemove: () => void }

function JournalLine({ entry, onSave, onRemove }: LineProps) {
  const [editing, setEditing] = useState<string | null>(null)
  return (
    <li>
      <p className="subtle">{journalKind(entry)}</p>
      {editing === null ? <p>{entry.text}</p>
        : <textarea aria-label={`What you know about ${entry.subject}`} rows={2} maxLength={500} value={editing}
          onChange={(event) => setEditing(event.target.value)} />}
      <div className="form-actions">
        {editing === null ? <>
          <button type="button" className="text-button" onClick={() => setEditing(entry.text)}>Correct</button>
          <button type="button" className="text-button" onClick={onRemove}>Remove</button>
        </> : <>
          <button type="button" className="text-button" disabled={!editing.trim()} onClick={() => void onSave(editing.trim()).then(() => setEditing(null))}>Save</button>
          <button type="button" className="text-button" onClick={() => setEditing(null)}>Cancel</button>
        </>}
      </div>
    </li>
  )
}

function AddNote({ onAdd }: { onAdd: (subject: string, text: string) => Promise<void> }) {
  const [subject, setSubject] = useState('')
  const [text, setText] = useState('')
  const ready = !!subject.trim() && !!text.trim()
  return (
    <form className="story-note-form" onSubmit={(event) => { event.preventDefault(); if (ready) void onAdd(subject.trim(), text.trim()).then(() => { setSubject(''); setText('') }) }}>
      <input aria-label="About" placeholder="About whom or what" maxLength={120} value={subject} onChange={(event) => setSubject(event.target.value)} />
      <input aria-label="What you know" placeholder="What you know" maxLength={500} value={text} onChange={(event) => setText(event.target.value)} />
      <button type="submit" className="button" disabled={!ready}>Add</button>
    </form>
  )
}
