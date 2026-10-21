import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { MapPin, RotateCcw, Send, Undo2 } from 'lucide-react'
import { api, newId } from '../../api'
import type { View } from '../../workspace'
import type { CitySummary, Story as StoryData, StoryBack, StoryMessage, StoryScene } from '../../types'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { InfoTip } from '../../components/InfoTip'
import { AiFooter, CrisisNote } from '../../components/Safety'
import { aroundText, placeGroups, rollText, sceneTime, spotsText, whereText } from './storyText'
import { StoryPeople } from './StoryPeople'
import { CityOptions } from '../world/CityOptions'
import { AuthorsNote } from './AuthorsNote'
import { StorySheet } from './StorySheet'
import { StoryStart } from './StoryStart'
import { StoryBranches } from './StoryBranches'
import { StoryJournal } from './StoryJournal'

const STORY_KEY = ['story']
const OUT_OF_STORY = 'To step out of the story, start a message with OOC: or wrap it in ((double parentheses)).'

/** The story: the user's own story around the cities, told by a narrator. */
export function Story({ go }: { go: (view: View) => void }) {
  const story = useQuery({ queryKey: STORY_KEY, queryFn: () => api<StoryData>('/story') })
  const client = useQueryClient()
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState({ text: '', at: 0 })
  if (story.isPending) return <Loading label="Opening your story" />
  if (story.isError) return <ErrorNotice error={story.error} />
  const update = (data: StoryData) => client.setQueryData(STORY_KEY, data)
  const run = async (text: string | null, request: () => Promise<unknown>) => {
    setPending(text)
    setError('')
    try { await request() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work. Try again.') }
    finally { setPending(null); await Promise.all([client.invalidateQueries({ queryKey: STORY_KEY }), client.invalidateQueries({ queryKey: ['story-journal'] })]) }
  }
  const send = (text: string) => run(text, () => api('/story/messages', { text, client_id: newId() }))
  return (
    <section className="story" aria-labelledby="story-heading">
      <StoryHeader story={story.data} change={(request) => run(null, () => request().then(update))} />
      {!story.data.ready && <NoModel go={go} />}
      {!story.data.messages.length && pending === null ? <StoryStart onStarted={update} /> : <>
        <StoryLog messages={story.data.messages} pending={pending} onRetry={() => void run(null, () => api('/story/retry', {}))}
          onBack={(id) => void run(null, () => api<StoryBack>('/story/back', { message_id: id }).then((data) => { update(data); setDraft({ text: data.draft, at: Date.now() }) }))} />
        {error && <div className="story-notice"><Notice tone="error">{error}</Notice></div>}
        <StoryComposer key={draft.at} busy={pending !== null} draft={draft.text} onSend={(text) => void send(text)} />
      </>}
      <NewStory empty={!story.data.messages.length} onClear={() => run(null, () => api<StoryData>('/story', undefined, 'DELETE').then(update))} />
    </section>
  )
}

function NoModel({ go }: { go: (view: View) => void }) {
  return <div className="story-notice"><Notice action={<button type="button" className="text-button" onClick={() => go('settings/models')}>Open Models</button>}>
    Add a text model in Settings &gt; Models to tell the story.</Notice></div>
}

/** The scene, the sheet, the people met and the other branches; `change` runs a request that returns the story. */
function StoryHeader({ story, change }: { story: StoryData; change: (request: () => Promise<StoryData>) => Promise<void> }) {
  return (
    <header className="story-header">
      <h1 id="story-heading">Story</h1>
      <p className="subtle">Your own story around town, told by a narrator.</p>
      <SceneBar scene={story.scene} onMove={(body) => change(() => api<StoryData>('/story/scene', body, 'PUT'))} />
      {!!story.messages.length && <><StorySheet /><StoryJournal /></>}
      <StoryPeople people={story.people} onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))} />
      <StoryBranches branches={story.branches}
        onSwitch={(id) => void change(() => api<StoryData>(`/story/branches/${encodeURIComponent(id)}/switch`, {}))} />
    </header>
  )
}

function SceneBar({ scene, onMove }: { scene: StoryScene; onMove: (body: { city_id: string; place_id?: string }) => Promise<void> }) {
  const [moving, setMoving] = useState(false)
  return (
    <div className="story-scene">
      <p><MapPin aria-hidden="true" /> <strong>{whereText(scene)}</strong></p>
      <p className="subtle">{sceneTime(scene.local_time)}{scene.weather ? ` · ${scene.weather}` : ''}</p>
      {!!scene.place.spots?.length && <p className="subtle">{spotsText(scene.place.spots)}</p>}
      <p>{aroundText(scene.around)}</p>
      {moving ? <GoElsewhere scene={scene} onDone={() => setMoving(false)} onMove={onMove} />
        : <div className="form-actions">
          <button type="button" className="button" onClick={() => setMoving(true)}>Go somewhere else…</button>
        </div>}
    </div>
  )
}

interface GoProps { scene: StoryScene; onDone: () => void; onMove: (body: { city_id: string; place_id?: string }) => Promise<void> }

function GoElsewhere({ scene, onDone, onMove }: GoProps) {
  const cities = useQuery({ queryKey: ['world-cities'], queryFn: () => api<CitySummary[]>('/world/cities') })
  const [place, setPlace] = useState(scene.place.id)
  return (
    <div className="story-go form-actions">
      <label>City
        <select value={scene.city.id} onChange={(event) => void onMove({ city_id: event.target.value })}>
          <CityOptions cities={cities.data ?? [scene.city]} />
        </select>
      </label>
      <label>Place
        <select value={place} onChange={(event) => setPlace(event.target.value)}>
          {placeGroups(scene.places).map(([hood, places]) => (
            <optgroup key={hood} label={hood}>
              {places.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.kind})</option>)}
            </optgroup>))}
        </select>
      </label>
      <button type="button" className="button primary" onClick={() => void onMove({ city_id: scene.city.id, place_id: place }).then(onDone)}>Go</button>
      <button type="button" className="text-button" onClick={onDone}>Stay here</button>
    </div>
  )
}

interface LogProps { messages: StoryMessage[]; pending: string | null; onRetry: () => void; onBack: (id: string) => void }

function StoryLog({ messages, pending, onRetry, onBack }: LogProps) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'end' }) }, [messages.length, pending])
  const last = messages[messages.length - 1]
  return (
    <div className="story-log" aria-live="polite">
      {messages.map((message) => <StoryLine key={message.id} message={message} onBack={pending ? undefined : onBack} />)}
      {pending && <><p className="story-user">{pending}</p><p className="subtle">The narrator is writing…</p></>}
      {last?.status === 'failed' && !pending && <button type="button" className="text-button" onClick={onRetry}><RotateCcw aria-hidden="true" />Try again</button>}
      <div ref={end} />
    </div>
  )
}

/** `onBack` goes back to before a line of the player's, to send it again with new dice. */
function StoryLine({ message, onBack }: { message: StoryMessage; onBack?: (id: string) => void }) {
  if (message.role === 'scene') return <p className="story-move">{message.text}</p>
  if (message.role === 'user') return <>
    <p className="story-user">{message.text}</p>
    <div className="story-turn">
      {!!message.rolls?.length && <ul className="story-rolls" aria-label="Rolls">{message.rolls.map((roll, index) => <li key={index} title={roll.action}>{rollText(roll)}</li>)}</ul>}
      {onBack && <button type="button" className="text-button story-back" onClick={() => onBack(message.id)}
        title="Go back to before this line and send it again, with new dice. The story from here is kept as a branch."><Undo2 aria-hidden="true" />Go back here</button>}
    </div>
    {message.crisis_help && <CrisisNote />}
  </>
  if (message.status === 'failed') return <Notice tone="error">The narrator could not go on: {message.error}</Notice>
  return <div className="story-narration">{message.text.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}</div>
}

/** `draft` is a line taken back to send again; a new draft remounts the composer with it. */
function StoryComposer({ busy, draft, onSend }: { busy: boolean; draft: string; onSend: (text: string) => void }) {
  const [text, setText] = useState(draft)
  const submit = () => { if (text.trim() && !busy) { onSend(text.trim()); setText('') } }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit() }
  }
  return (<>
    <form className="composer story-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
      <AuthorsNote chat="story" name="The narrator" story />
      <label className="visually-hidden" htmlFor="story-text">What you do or say</label>
      <textarea id="story-text" rows={2} value={text} maxLength={40000} placeholder="What do you do or say?"
        onChange={(event) => setText(event.target.value)} onKeyDown={onKeyDown} />
      <InfoTip id="story-tip" label="the story" above text={`Enter sends, Shift+Enter adds a new line. ${OUT_OF_STORY}`} />
      <button type="submit" className="button primary" disabled={busy || !text.trim()}><Send aria-hidden="true" />Send</button>
    </form>
    <AiFooter />
  </>)
}

function NewStory({ empty, onClear }: { empty: boolean; onClear: () => Promise<void> }) {
  const [asking, setAsking] = useState(false)
  if (empty) return null
  return (
    <div className="story-footer">
      <button type="button" className="text-button" onClick={() => setAsking(true)}>Start a new story…</button>
      {asking && <ConfirmDialog title="Start a new story?" onClose={() => setAsking(false)} actions={<>
        <button type="button" className="button" onClick={() => setAsking(false)}>Cancel</button>
        <button type="button" className="button primary" onClick={() => void onClear().then(() => setAsking(false))}>Start a new story</button>
      </>}>
        <p>The story so far and the people you&apos;ve met in it are cleared for good. You stay where you are.</p>
      </ConfirmDialog>}
    </div>
  )
}
