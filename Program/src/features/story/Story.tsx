import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, Bookmark, MapPin, RotateCcw, Send, Settings2, Timer, Undo2 } from 'lucide-react'
import { api, newId, streamApi } from '../../api'
import type { View } from '../../workspace'
import type { BandStep, CitySummary, Story as StoryData, StoryBack, StoryMessage, StoryScene, TurnEvent, TurnSoFar } from '../../types'
import { Loading, Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { InfoTip } from '../../components/InfoTip'
import { AiFooter, CrisisNote } from '../../components/Safety'
import { aroundText, fightText, journeyTo, NO_TURN, paceText, placeGroups, sceneTime, spotsText, turnAfter, whereText } from './storyText'
import { RollCard, TurnLive } from './StoryTurn'
import { StoryPeople } from './StoryPeople'
import { CityOptions } from '../world/CityOptions'
import { AuthorsNote } from './AuthorsNote'
import { StorySheet } from './StorySheet'
import { StoryStart } from './StoryStart'
import { StoryBranches } from './StoryBranches'
import { StoryJournal } from './StoryJournal'
import { StoryChapters } from './StoryChapters'
import { StoryNotebook } from './StoryNotebook'
import { StoryGear } from './StoryGear'
import { StoryIntensity } from './StoryIntensity'
import { HiddenValues } from '../settings/HiddenValues'
import { StoryInjuries } from './StoryInjuries'
import { StoryPowers } from './StoryPowers'
import { StoryNarration } from './StoryNarration'
import { StoryMap } from './StoryMap'

const STORY_KEY = ['story']
/** Matches the stylesheet's breakpoint for the side panel. */
const WIDE = '(min-width: 1100px)'
const OUT_OF_STORY = 'To step out of the story, start a message with OOC: or wrap it in ((double parentheses)).'

/** The story: the user's own story around the cities, told by a narrator. */
export function Story({ go }: { go: (view: View) => void }) {
  const story = useQuery({ queryKey: STORY_KEY, queryFn: () => api<StoryData>('/story') })
  const client = useQueryClient()
  const [pending, setPending] = useState<string | null>(null)
  // The narration so far while it streams in (dungeon/pace.py).
  const [streamed, setStreamed] = useState('')
  // The turn's stages and rolls so far, before and around the narration (dungeon/story.py answer).
  const [turn, setTurn] = useState<TurnSoFar>(NO_TURN)
  const [error, setError] = useState('')
  // How many lines the story had when the turn began: once the saved story has more, the turn is in it.
  const [since, setSince] = useState(0)
  const [draft, setDraft] = useState({ text: '', at: 0 })
  if (story.isPending) return <Loading label="Opening your story" />
  if (story.isError) return <ErrorNotice error={story.error} />
  const update = (data: StoryData) => client.setQueryData(STORY_KEY, data)
  // The turn stays on screen as streamed until the saved story has come back, so the narration never blinks out;
  // `streamed` is kept after the turn, as the draft the saved text is compared with (StoryNarration `draft`).
  const run = async (text: string | null, request: () => Promise<unknown>) => {
    setSince(story.data.messages.length)
    setPending(text)
    setStreamed('')
    setTurn(NO_TURN)
    setError('')
    try { await request() } catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not work. Try again.') }
    finally {
      await Promise.all([client.invalidateQueries({ queryKey: STORY_KEY }), client.invalidateQueries({ queryKey: ['story-journal'] }), client.invalidateQueries({ queryKey: ['story-gear'] }), client.invalidateQueries({ queryKey: ['story-sheet'] })])
        .finally(() => setPending(null))
    }
  }
  const grow = (piece: string) => setStreamed((before) => before + piece)
  const note = (event: unknown) => setTurn((before) => turnAfter(before, event as TurnEvent))
  const send = (text: string) => run(text, () => streamApi('/story/messages/stream', { text, client_id: newId() }, grow, note))
  const change = (request: () => Promise<StoryData>) => run(null, () => request().then(update))
  return (
    <section className="story" aria-labelledby="story-heading">
      <div className="story-main">
        <StoryHeader story={story.data} change={change} onDraft={(text) => setDraft({ text, at: Date.now() })} />
        {!story.data.ready && <NoModel go={go} />}
        {!story.data.messages.length && pending === null ? <StoryStart onStarted={update} /> : <>
          <StoryLog messages={story.data.messages} pending={story.data.messages.length > since ? null : pending} streamed={streamed} turn={turn} bands={story.data.bands}
            onRetry={() => void run('', () => streamApi('/story/retry/stream', {}, grow, note))}
            onRewrite={(id, passage, note) => change(() => api<StoryData>(`/story/messages/${id}/rewrite`, { passage, note }))}
            onSwitch={(id) => change(() => api<StoryData>(`/story/messages/${id}/switch`, {}))}
            onBack={story.data.campaign?.ironman ? undefined : (id) => void run(null, () => api<StoryBack>('/story/back', { message_id: id }).then((data) => { update(data); setDraft({ text: data.draft, at: Date.now() }) }))}
            onBookmark={(id, name) => change(() => api<StoryData>('/story/bookmarks', { message_id: id, name }))} />
          {error && <div className="story-notice"><Notice tone="error">{error}</Notice></div>}
          <StoryComposer key={draft.at} busy={pending !== null} draft={draft.text} onSend={(text) => void send(text)} />
        </>}
        <NewStory empty={!story.data.messages.length} onClear={() => run(null, () => api<StoryData>('/story', undefined, 'DELETE').then(update))} />
      </div>
      <StoryPanel story={story.data} change={change} onTravel={(name) => setDraft({ text: `I set out for ${name}.`, at: Date.now() })}
        onBack={(data) => setDraft({ text: data.draft, at: Date.now() })} />
    </section>
  )
}

function NoModel({ go }: { go: (view: View) => void }) {
  return <div className="story-notice"><Notice action={<button type="button" className="text-button" onClick={() => go('settings/models')}>Open Models</button>}>
    Add a text model in Settings &gt; Models to tell the story.</Notice></div>
}

/** Where and when the story is, and the fight. The scene line is the header; the title is for screen readers. */
interface HeaderProps { story: StoryData; change: (request: () => Promise<StoryData>) => Promise<void>; onDraft: (text: string) => void }

function StoryHeader({ story, change, onDraft }: HeaderProps) {
  const fight = fightText(story.fight)
  return (
    <header className="story-header">
      <h1 id="story-heading" className="visually-hidden">Story</h1>
      <SceneBar scene={story.scene} journeys={story.map?.places.filter((place) => !place.here).map((place) => place.name) ?? []} onDraft={onDraft}
        onMove={(body) => change(() => api<StoryData>('/story/scene', body, 'PUT'))} />
      {fight && <p className={story.fight.fight || story.fight.dead ? 'story-fight' : 'subtle'} role="status">{fight}</p>}
    </header>
  )
}

/** The fixed side panel (beside the story on a wide screen, above it on a narrow one): the sheet, the pack and the
 * shop window, the journal, the map, the people met and the other branches. The free grid comes in Milestone 6. */
interface PanelProps { story: StoryData; change: (request: () => Promise<StoryData>) => Promise<void>; onTravel: (name: string) => void; onBack: (data: StoryBack) => void }

function StoryPanel({ story, change, onTravel, onBack }: PanelProps) {
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: STORY_KEY })
  // Beside the story there is room to show the sheet, pack and journal open; above it they start folded.
  const [wide] = useState(() => window.matchMedia?.(WIDE).matches ?? false)
  return (
    <aside className="story-panel" aria-label="Your character and what you know">
      {!!story.messages.length && <><StorySheet open={wide} /><StoryGear open={wide} onTrade={() => void refresh()} /><StoryJournal open={wide} /></>}
      {!!story.messages.length && <StoryMap map={story.map} open={wide} onTravel={onTravel} />}
      {!!story.messages.length && <StoryPowers factions={story.factions ?? []} tier={story.tier} />}
      <StoryPeople people={story.people} onFind={(key) => void change(() => api<StoryData>('/story/find', { key }))} />
      {story.campaign && <StoryChapters campaign={story.campaign} change={change} onBack={onBack} />}
      {!story.campaign?.ironman && <StoryBranches branches={story.branches}
        onSwitch={(id) => void change(() => api<StoryData>(`/story/branches/${encodeURIComponent(id)}/switch`, {}))} />}
      {!!story.messages.length && <StoryNotebook />}
      {/* Tone and rules are set once and changed now and then, so they fold away below what play needs. They are this
          campaign's rules, so they live here rather than in Settings (src/features/settings/sections.ts ELSEWHERE). */}
      <details className="story-people story-dials">
        <summary id="story-dials-heading"><Settings2 aria-hidden="true" />Tone and rules</summary>
        <StoryIntensity intensity={story.intensity} onSaved={() => void refresh()} />
        <StoryInjuries persistence={story.injury_persistence ?? 'permanent'} onSaved={() => void refresh()} />
        <HiddenValues />
      </details>
    </aside>
  )
}

interface SceneProps { scene: StoryScene; journeys: string[]; onDraft: (text: string) => void; onMove: (body: { city_id: string; place_id?: string }) => Promise<void> }

function SceneBar({ scene, journeys, onDraft, onMove }: SceneProps) {
  const [moving, setMoving] = useState(false)
  return (
    <div className="story-scene">
      <div className="story-where">
        <p><MapPin aria-hidden="true" /> <strong>{whereText(scene)}</strong></p>
        {!moving && <button type="button" className="text-button" onClick={() => setMoving(true)}>Go somewhere else…</button>}
      </div>
      <p className="subtle">{sceneTime(scene.local_time)}{scene.weather ? ` · ${scene.weather}` : ''}</p>
      {!!scene.place.spots?.length && <p className="subtle">{spotsText(scene.place.spots)}</p>}
      <p>{aroundText(scene.around)}</p>
      {moving && <GoElsewhere scene={scene} journeys={journeys} onDone={() => setMoving(false)} onDraft={onDraft} onMove={onMove} />}
    </div>
  )
}

interface GoProps extends Omit<SceneProps, 'scene'> { scene: StoryScene; onDone: () => void }

/** Somewhere on the travel map (a town, a keep) is a journey: it writes "I set out for…" into the composer, like the
 *  map does, so the road takes its hours and can bring trouble (dungeon/travel.py). A place across town is a cut. */
function GoElsewhere({ scene, journeys, onDone, onDraft, onMove }: GoProps) {
  const cities = useQuery({ queryKey: ['world-cities'], queryFn: () => api<CitySummary[]>('/world/cities') })
  const [city, setCity] = useState(scene.city.id)
  const [place, setPlace] = useState(scene.place.id)
  const here = city === scene.city.id
  const go = () => {
    const name = here ? scene.places.find((item) => item.id === place)?.name : cities.data?.find((item) => item.id === city)?.name
    const journey = journeyTo(journeys, name)
    if (journey) { onDraft(`I set out for ${journey}.`); onDone() }
    else void onMove(here ? { city_id: city, place_id: place } : { city_id: city }).then(onDone)
  }
  return (
    <div className="story-go form-actions">
      <label>City
        <select value={city} onChange={(event) => setCity(event.target.value)}>
          <CityOptions cities={cities.data ?? [scene.city]} />
        </select>
      </label>
      {here && <label>Place
        <select value={place} onChange={(event) => setPlace(event.target.value)}>
          {placeGroups(scene.places).map(([hood, places]) => (
            <optgroup key={hood} label={hood}>
              {places.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.kind})</option>)}
            </optgroup>))}
        </select>
      </label>}
      <button type="button" className="button primary" onClick={go}>Go</button>
      <button type="button" className="text-button" onClick={onDone}>Stay here</button>
    </div>
  )
}

interface Rewrites { onRewrite: (id: string, passage: string, note: string) => Promise<void>; onSwitch: (id: string) => Promise<void> }
interface LogProps extends Rewrites {
  messages: StoryMessage[]; pending: string | null; streamed: string; turn: TurnSoFar; bands?: BandStep[] | null
  onRetry: () => void; onBack?: (id: string) => void; onBookmark: (id: string, name: string) => Promise<void>
}

/** How near the bottom (px) still counts as reading the newest text, so the log keeps following it. */
const FOLLOW = 80

/** Follows new text only while the reader is at the bottom; scrolled up to reread, they keep their place, and
 *  `behind` says there is newer text than what they last read to. Sending a line jumps to it wherever they were. */
function useFollow(shown: string, pending: string | null) {
  const log = useRef<HTMLDivElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const [atEnd, setAtEnd] = useState(true)
  const [readTo, setReadTo] = useState(shown)
  // At the bottom the reader has read everything shown (set while rendering, React's pattern for derived state).
  if (atEnd && readTo !== shown) setReadTo(shown)
  const toEnd = () => end.current?.scrollIntoView?.({ block: 'end' })
  const onScroll = () => {
    const box = log.current
    if (box) setAtEnd(box.scrollHeight - box.scrollTop - box.clientHeight < FOLLOW)
  }
  useEffect(() => { if (atEnd) end.current?.scrollIntoView?.({ block: 'end' }) }, [shown, atEnd])
  useEffect(() => { if (pending !== null) end.current?.scrollIntoView?.({ block: 'end' }) }, [pending])
  return { log, end, onScroll, toEnd, behind: !atEnd && readTo !== shown }
}

function StoryLog({ messages, pending, streamed, turn, bands, onRetry, onBack, onBookmark, onRewrite, onSwitch }: LogProps) {
  const { log, end, onScroll, toEnd, behind } = useFollow(`${messages.length}:${streamed.length}`, pending)
  const last = messages[messages.length - 1]
  return (
    <div className="story-log" aria-live="polite" ref={log} onScroll={onScroll}>
      {messages.map((message) => <StoryLine key={message.id} message={message} bands={bands} onBack={pending ? undefined : onBack}
        onBookmark={pending ? undefined : onBookmark}
        rewrites={pending === null ? { onRewrite, onSwitch } : undefined} draft={pending === null && message === last ? streamed : undefined} />)}
      {pending && <p className="story-user">{pending}</p>}
      {pending !== null && <TurnLive turn={turn} writing={!!streamed} />}
      {pending !== null && !!streamed && <div className="story-narration">{streamed.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}</div>}
      {last?.status === 'failed' && !pending && <button type="button" className="text-button" onClick={onRetry}><RotateCcw aria-hidden="true" />Try again</button>}
      <div ref={end} />
      {behind && <button type="button" className="button story-newer" onClick={toEnd}><ArrowDown aria-hidden="true" />New text below</button>}
    </div>
  )
}

/** `onBack` goes back to before a line of the player's, to send it again with new dice; `rewrites` rewords a
 *  narration (none while a turn is being told). */
interface LineProps { message: StoryMessage; bands?: BandStep[] | null; onBack?: (id: string) => void; onBookmark?: (id: string, name: string) => Promise<void>; rewrites?: Rewrites; draft?: string }

function StoryLine({ message, bands, onBack, onBookmark, rewrites, draft }: LineProps) {
  if (message.role === 'scene') return <p className="story-move">{message.text}</p>
  if (message.role === 'user') return <>
    <p className="story-user" id={`line-${message.id}`}>{message.text}</p>
    <div className="story-turn">
      {message.rolls?.map((roll, index) => <RollCard key={index} roll={roll} bands={bands} />)}
      <div className="story-turn-actions">
        {/* How long the turn took is for tuning, not the story: it waits in a tooltip until the dice log ships. */}
        {message.pace && <span className="story-pace" title={paceText(message.pace)}><Timer aria-hidden="true" /><span className="visually-hidden">{paceText(message.pace)}</span></span>}
        {onBack && <button type="button" className="text-button story-back" onClick={() => onBack(message.id)}
          title="Go back to before this line and send it again, with new dice. The story from here is kept as a branch."><Undo2 aria-hidden="true" />Go back here</button>}
        {onBookmark && <BookmarkButton onSave={(name) => onBookmark(message.id, name)} />}
      </div>
    </div>
    {message.crisis_help && <CrisisNote />}
  </>
  if (message.status === 'failed') return <Notice tone="error">The narrator could not go on: {message.error}</Notice>
  return <StoryNarration message={message} draft={draft} {...rewrites} />
}

/** Names this moment to find it again (dungeon/chapters.py bookmarks). */
function BookmarkButton({ onSave }: { onSave: (name: string) => Promise<void> }) {
  const [name, setName] = useState<string | null>(null)
  if (name === null) return <button type="button" className="text-button" onClick={() => setName('')}><Bookmark aria-hidden="true" />Bookmark</button>
  return (
    <form className="story-bookmark" onSubmit={(event) => { event.preventDefault(); if (name.trim()) void onSave(name.trim()).then(() => setName(null)) }}>
      <input aria-label="Name this moment" placeholder="Name this moment" maxLength={80} value={name} onChange={(event) => setName(event.target.value)} autoFocus />
      <button type="submit" className="text-button" disabled={!name.trim()}>Save</button>
      <button type="button" className="text-button" onClick={() => setName(null)}>Cancel</button>
    </form>
  )
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
