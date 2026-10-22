import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Image, MapPin, RefreshCw, User, Users } from 'lucide-react'
import { api } from '../../api'
import { Notice } from '../../components/Feedback'
import type { ArtKind, StoryArt as Picture, StoryPerson } from '../../types'
import { artLabel, artStatus, making } from './artText'
import { askForDrawer } from './scene'

const ART_KEY = ['story-art']

/** Pictures on request (dungeon/art.py): you, someone you met, this place, or the whole scene. Each is built from what
 *  the game tracks and made by the image backends in Settings; one goes out of date when what it shows changes. */
export function StoryArt({ people, place, open }: { people: StoryPerson[]; place: { key: string; name: string }; open?: boolean }) {
  const client = useQueryClient()
  const gallery = useQuery({ queryKey: ART_KEY, queryFn: () => api<{ art: Picture[] }>('/story/art'),
    refetchInterval: (query) => making(query.state.data?.art ?? []) ? 2000 : false })
  const [who, setWho] = useState('')
  const [error, setError] = useState('')
  const ask = async (kind: ArtKind, subject = '') => {
    setError('')
    try { client.setQueryData(ART_KEY, await api<{ art: Picture[] }>('/story/art', { kind, subject })) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That picture was not asked for.') }
  }
  const items = gallery.data?.art ?? []
  return (
    <details className="story-people story-art" open={open}>
      <summary>Pictures ({items.filter((item) => item.url).length})</summary>
      <div className="form-actions">
        <button type="button" className="button" onClick={() => void ask('portrait', 'player')}><User aria-hidden="true" />Picture me</button>
        <button type="button" className="button" onClick={() => void ask('place')}><MapPin aria-hidden="true" />This place</button>
        <button type="button" className="button" onClick={() => void ask('scene')}><Image aria-hidden="true" />The scene</button>
      </div>
      {people.length > 0 && <div className="form-actions">
        <select aria-label="Someone you met" value={who} onChange={(event) => setWho(event.target.value)}>
          <option value="">Someone you met…</option>
          {people.map((person) => <option key={person.key} value={person.key}>{person.name}</option>)}
        </select>
        <button type="button" className="button" disabled={!who} onClick={() => void ask('portrait', who)}><Users aria-hidden="true" />Picture them</button>
      </div>}
      {error && <Notice tone="error">{error}</Notice>}
      <ul className="art-gallery">
        {items.map((item) => <ArtCard key={item.id} item={item} label={artLabel(item, people, item.subject === place.key ? place.name : '')}
          onAgain={() => void ask(item.kind, item.kind === 'portrait' || item.kind === 'passage' ? item.subject : '')} />)}
      </ul>
    </details>
  )
}

function ArtCard({ item, label, onAgain }: { item: Picture; label: string; onAgain: () => void }) {
  const status = artStatus(item)
  return (
    <li className="art-card">
      {item.url && <img src={item.url} alt={label} loading="lazy" width={item.width ?? undefined} height={item.height ?? undefined} />}
      <p><strong>{label}</strong>{item.reference && <span className="subtle"> · their likeness</span>}</p>
      {status && <p className={item.status === 'failed' || item.status === 'refused' ? 'hidden-warning' : 'subtle'}>{status}</p>}
      {(item.stale || item.status === 'failed') && <button type="button" className="text-button" onClick={onAgain}><RefreshCw aria-hidden="true" />Make it again</button>}
    </li>
  )
}

/** Pictures a passage of the story, then opens Pictures to show it. */
export function IllustrateButton({ messageId }: { messageId: string }) {
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const illustrate = async () => {
    setBusy(true)
    try { client.setQueryData(ART_KEY, await api<{ art: Picture[] }>('/story/art', { kind: 'passage', subject: messageId })) }
    finally { setBusy(false); askForDrawer('art') }
  }
  return <button type="button" className="text-button story-back" disabled={busy} onClick={() => void illustrate()}
    title="Make a picture of this passage with your image backend."><Image aria-hidden="true" />{busy ? 'Picturing…' : 'Picture this'}</button>
}
