import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { PersonaGender, Story as StoryData, StoryStart as StartChoices } from '../../types'
import { TextArea, TextInput } from '../../components/Fields'
import { Stepper } from '../../components/NumberFields'
import { Loading, Notice } from '../../components/Feedback'
import { GENDERS } from '../worlds/worldsText'
import { WORLDS_KEY } from '../worlds/useWorlds'
import { pointsLeft, pointsText, premadeLine, startingStats } from './storyText'

/** Campaign start (dungeon/campaign.py): play a premade character from this town, or make your own. */
export function StoryStart({ onStarted }: { onStarted: (data: StoryData) => void }) {
  const choices = useQuery({ queryKey: ['story-start'], queryFn: () => api<StartChoices>('/story/start') })
  const client = useQueryClient()
  const [making, setMaking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (!choices.data) return <Loading label="Finding who you could be" />
  const begin = async (body: object) => {
    setBusy(true)
    setError('')
    try {
      onStarted(await api<StoryData>('/story/start', body))
      await Promise.all([client.invalidateQueries({ queryKey: ['story-sheet'] }), client.invalidateQueries({ queryKey: WORLDS_KEY })])
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The story did not start. Try again.') }
    finally { setBusy(false) }
  }
  const { premades } = choices.data
  const own = making || !premades.length
  return (
    <section className="story-start" aria-labelledby="story-start-heading">
      <h2 id="story-start-heading">Who are you?</h2>
      {!own && <>
        <p className="subtle">Play someone from this town, or make your own.</p>
        <ul className="story-premades">
          {premades.map((premade) => (
            <li key={premade.id}>
              <strong>{premade.name}</strong> <span className="subtle">{premadeLine(premade)}</span>
              <p>{premade.about}</p>
              <button type="button" className="button primary" disabled={busy} onClick={() => void begin({ premade_id: premade.id })}>Play as {premade.name.split(' ')[0]}</button>
            </li>
          ))}
        </ul>
        <button type="button" className="button" onClick={() => setMaking(true)}>Make your own…</button>
      </>}
      {own && <MakeYourOwn choices={choices.data} busy={busy} onBegin={(body) => void begin(body)}
        onBack={premades.length ? () => setMaking(false) : undefined} />}
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}

interface MakeProps { choices: StartChoices; busy: boolean; onBegin: (body: object) => void; onBack?: () => void }

function MakeYourOwn({ choices, busy, onBegin, onBack }: MakeProps) {
  const [name, setName] = useState('')
  const [gender, setGender] = useState<PersonaGender>('')
  const [age, setAge] = useState('')
  const [about, setAbout] = useState('')
  const [stats, setStats] = useState(() => startingStats(choices))
  const [min, max] = choices.range
  const left = pointsLeft(stats, choices.points)
  const years = age ? Number(age) : null
  const valid = !!name.trim() && left >= 0 && (years === null || (years >= 18 && years <= 120))
  const submit = () => onBegin({ persona: { name: name.trim(), gender, age: years, about: about.trim() }, stats })
  return (
    <form className="story-make" onSubmit={(event) => { event.preventDefault(); if (valid) submit() }}>
      <TextInput label="Name" value={name} onChange={setName} required maxLength={80} />
      <label className="field">Gender
        <select value={gender} onChange={(event) => setGender(event.target.value as PersonaGender)}>
          {GENDERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <TextInput label="Age" type="number" value={age} onChange={setAge} min={18} max={120} />
      <TextArea label="About you" hint="Who they are, what they want, what they're running from. The narrator only knows what you write here."
        value={about} onChange={setAbout} rows={4} maxLength={2000} />
      <p className={left < 0 ? 'story-points over' : 'story-points'}>{pointsText(left, choices.points)}</p>
      <div className="story-stats">
        {choices.stat_names.map((stat) => (
          <Stepper key={stat} label={stat} value={stats[stat]} min={min} max={max} hint={choices.meanings[stat]}
            format={String} onChange={(value) => setStats({ ...stats, [stat]: value })} />
        ))}
      </div>
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={busy || !valid}>Begin the story</button>
        {onBack && <button type="button" className="button" onClick={onBack}>Back</button>}
      </div>
    </form>
  )
}
