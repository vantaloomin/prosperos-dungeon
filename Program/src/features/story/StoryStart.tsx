import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { IronswornChoices, LegacyCandidate, LegacyRole, PersonaGender, Ruleset, Srd52Choices, Story as StoryData, StoryArc, StoryHand, StoryPace, StoryStart as StartChoices } from '../../types'
import { Field, TextArea, TextInput, Toggle } from '../../components/Fields'
import { Stepper } from '../../components/NumberFields'
import { Loading, Notice } from '../../components/Feedback'
import { GENDERS } from '../worlds/worldsText'
import { WORLDS_KEY } from '../worlds/useWorlds'
import { ARC_NAMES, arrayPlaced, HAND_NAMES, LEGACY_ROLES, PACE_NAMES, skillChoices, skillId, pointsLeft, pointsText, premadeLine, startingStats } from './storyText'

/** Campaign start (dungeon/campaign.py): play a premade character from this town, or make your own. */
export function StoryStart({ onStarted }: { onStarted: (data: StoryData) => void }) {
  const choices = useQuery({ queryKey: ['story-start'], queryFn: () => api<StartChoices>('/story/start') })
  const client = useQueryClient()
  const [making, setMaking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [arc, setArc] = useState<StoryArc | null>(null)
  const [pace, setPace] = useState<StoryPace | null>(null)
  const [hand, setHand] = useState<StoryHand | null>(null)
  const [ironman, setIronman] = useState(false)
  const [legacy, setLegacy] = useState<Legacy | null>(null)
  const [ruleset, setRuleset] = useState<Ruleset | null>(null)
  if (!choices.data) return <Loading label="Finding who you could be" />
  const begin = async (body: object) => {
    setBusy(true)
    setError('')
    try {
      onStarted(await api<StoryData>('/story/start', { ...body, ...given({ arc, pace, hand, legacy, ruleset }), ironman }))
      await Promise.all([client.invalidateQueries({ queryKey: ['story-sheet'] }), client.invalidateQueries({ queryKey: WORLDS_KEY })])
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The story did not start. Try again.') }
    finally { setBusy(false) }
  }
  const { premades, arc: world } = choices.data
  const own = making || !premades.length
  return (
    <section className="story-start" aria-labelledby="story-start-heading">
      <h2 id="story-start-heading">Who are you?</h2>
      {world && <div className="story-arc">
        <Field label="How far you can rise" hint="The work, foes and places that come to you grow with your name, up to this.">
          {(id, describedBy) => <select id={id} value={arc ?? world.arc} aria-describedby={describedBy} onChange={(event) => setArc(event.target.value as StoryArc)}>
            {(Object.entries(ARC_NAMES) as [StoryArc, string][]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>}
        </Field>
        <Field label="How fast">
          {(id) => <select id={id} value={pace ?? world.pace} onChange={(event) => setPace(event.target.value as StoryPace)}>
            {(Object.entries(PACE_NAMES) as [StoryPace, string][]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>}
        </Field>
        <Field label="How hard the story pushes" hint="How a game master's hand steers toward the larger story. It never decides what you do, or the dice.">
          {(id, describedBy) => <select id={id} value={hand ?? world.hand ?? 'guiding'} aria-describedby={describedBy} onChange={(event) => setHand(event.target.value as StoryHand)}>
            {(Object.entries(HAND_NAMES) as [StoryHand, string][]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>}
        </Field>
      </div>}
      <Toggle label="Ironman" hint="No going back for this whole campaign: no earlier line, no other branch. If your character dies, the story ends there."
        checked={ironman} onChange={setIronman} />
      <RulesetPick choices={choices.data} value={ruleset} onChange={setRuleset} />
      <LegacyPick candidates={choices.data.legacy ?? []} value={legacy} onChange={setLegacy} />
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
      {own && <MakeYourOwn choices={choices.data} ruleset={ruleset ?? choices.data.ruleset} busy={busy} onBegin={(body) => void begin(body)}
        onBack={premades.length ? () => setMaking(false) : undefined} />}
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}

interface MakeProps { choices: StartChoices; ruleset?: Ruleset; busy: boolean; onBegin: (body: object) => void; onBack?: () => void }

function MakeYourOwn({ choices, ruleset, busy, onBegin, onBack }: MakeProps) {
  const [name, setName] = useState('')
  const [gender, setGender] = useState<PersonaGender>('')
  const [age, setAge] = useState('')
  const [about, setAbout] = useState('')
  const [stats, setStats] = useState(() => startingStats(choices))
  const [build, setBuild] = useState<Build | null>(null)
  const [iron, setIron] = useState<IronBuild | null>(null)
  const years = age ? Number(age) : null
  const five = ruleset === 'srd52' && !!choices.srd52
  const sworn = ruleset === 'ironsworn' && !!choices.ironsworn
  const valid = !!name.trim() && builtFor(five ? build : sworn ? iron : true, pointsLeft(stats, choices.points)) && adultAge(years)
  const submit = () => onBegin({ persona: { name: name.trim(), gender, age: years, about: about.trim() }, ...(five ? { build } : sworn ? { ironsworn: iron } : { stats }) })
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
      <RulesBuild choices={choices} five={five} sworn={sworn} stats={stats} onStats={setStats} onBuild={setBuild} onIron={setIron} />
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={busy || !valid}>Begin the story</button>
        {onBack && <button type="button" className="button" onClick={onBack}>Back</button>}
      </div>
    </form>
  )
}

/** Whether the made character's sheet is ready: a 5E or Ironsworn build chosen, else MARVEL's points not overspent. */
function builtFor(build: unknown, left: number): boolean {
  return build === true ? left >= 0 : !!build
}

interface RulesBuildProps {
  choices: StartChoices; five: boolean; sworn: boolean; stats: Record<string, number>
  onStats: (stats: Record<string, number>) => void; onBuild: (build: Build | null) => void; onIron: (build: IronBuild | null) => void
}

/** The character's sheet in the campaign's ruleset. */
function RulesBuild({ choices, five, sworn, stats, onStats, onBuild, onIron }: RulesBuildProps) {
  if (five && choices.srd52) return <Srd52Build choices={choices.srd52} onChange={onBuild} />
  if (sworn && choices.ironsworn) return <IronswornBuild choices={choices.ironsworn} onChange={onIron} />
  return <MarvelStats choices={choices} stats={stats} onChange={onStats} />
}

type IronBuild = { stats: Record<string, number>; assets: string[] }

/** An Ironsworn character (dungeon/rules/ironsworn.py build): 3, 2, 2, 1 and 1 on the five stats, three assets. */
function IronswornBuild({ choices, onChange }: { choices: IronswornChoices; onChange: (build: IronBuild | null) => void }) {
  const [stats, setStats] = useState<Record<string, number>>(() => Object.fromEntries(choices.stats.map((stat, index) => [stat.id, choices.array[index]])))
  const [picks, setPicks] = useState<string[]>([])
  const report = (next: IronBuild) => onChange(arrayPlaced(next.stats, choices.array) && next.assets.length === choices.count ? next : null)
  const place = (stat: string, value: number) => { const next = { ...stats, [stat]: value }; setStats(next); report({ stats: next, assets: picks }) }
  const toggle = (asset: string) => {
    const next = picks.includes(asset) ? picks.filter((item) => item !== asset) : [...picks, asset].slice(-choices.count)
    setPicks(next)
    report({ stats, assets: next })
  }
  const categories = [...new Set(choices.assets.map((asset) => asset.category))]
  return (
    <fieldset className="story-build">
      <legend>Your Ironsworn character</legend>
      <p className="subtle">Place 3, 2, 2, 1 and 1, one on each stat.</p>
      <div className="story-abilities">
        {choices.stats.map((stat) => <label key={stat.id} className="field" title={stat.about}>{stat.name}
          <select value={stats[stat.id]} onChange={(event) => place(stat.id, Number(event.target.value))}>
            {[...new Set(choices.array)].map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>)}
      </div>
      {!arrayPlaced(stats, choices.array) && <p className="story-points over">Use 3 once, 2 twice and 1 twice.</p>}
      <p className="subtle">Choose {choices.count} assets ({picks.length} chosen).</p>
      {categories.map((category) => <details key={category}>
        <summary>{category}</summary>
        <div className="story-skills">
          {choices.assets.filter((asset) => asset.category === category).map((asset) => <label key={asset.id} className="checkbox" title={asset.about}>
            <input type="checkbox" checked={picks.includes(asset.id)} onChange={() => toggle(asset.id)} />{asset.name}
          </label>)}
        </div>
      </details>)}
      <p className="subtle story-attribution">{choices.attribution}</p>
    </fieldset>
  )
}

type Legacy = { world_id: string; role: LegacyRole }

/** An earlier campaign's character, brought in as this world's history (dungeon/legacy.py). */
function LegacyPick({ candidates, value, onChange }: { candidates: LegacyCandidate[]; value: Legacy | null; onChange: (value: Legacy | null) => void }) {
  if (!candidates.length) return null
  const line = (item: LegacyCandidate) => `${item.name}, from ${item.world}${item.dead ? ' (died)' : ''}`
  return (
    <div className="story-arc">
      <Field label="An earlier story" hint="Bring a character from another world's story into this one, as history.">
        {(id, describedBy) => <select id={id} value={value?.world_id ?? ''} aria-describedby={describedBy}
          onChange={(event) => onChange(event.target.value ? { world_id: event.target.value, role: value?.role ?? 'legend' } : null)}>
          <option value="">None</option>
          {candidates.map((item) => <option key={item.world_id} value={item.world_id}>{line(item)}</option>)}
        </select>}
      </Field>
      {value && <Field label="They come back as">
        {(id) => <select id={id} value={value.role} onChange={(event) => onChange({ ...value, role: event.target.value as LegacyRole })}>
          {(Object.entries(LEGACY_ROLES) as [LegacyRole, string][]).map(([role, label]) => <option key={role} value={role}>{label}</option>)}
        </select>}
      </Field>}
    </div>
  )
}

/** The ruleset the campaign is played in (dungeon/sheet.py): chosen now and locked for the whole campaign. */
function RulesetPick({ choices, value, onChange }: { choices: StartChoices; value: Ruleset | null; onChange: (value: Ruleset) => void }) {
  if (!choices.rulesets || choices.rulesets.length < 2) return null
  return (
    <Field label="Rules" hint="How the dice decide. Chosen now for the whole campaign; it cannot change later.">
      {(id, describedBy) => <select id={id} value={value ?? choices.ruleset ?? 'marvel'} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value as Ruleset)}>
        {choices.rulesets?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>}
    </Field>
  )
}

type Build = { class_id: string; species_id: string; background_id: string; scores: Record<string, number>; skills: string[] }

/** A 5E character (dungeon/rules/srd52.py build): class, species and background from the pack, the standard array
 * placed on the six abilities (the background then adds +2 and +1), and the class's skills. */
function Srd52Build({ choices, onChange }: { choices: Srd52Choices; onChange: (build: Build | null) => void }) {
  const [classId, setClassId] = useState(choices.classes[0].id)
  const [speciesId, setSpeciesId] = useState(choices.species[0].id)
  const [backgroundId, setBackgroundId] = useState(choices.backgrounds[0].id)
  const [scores, setScores] = useState<Record<string, number>>(() => Object.fromEntries(choices.abilities.map((ability, index) => [ability.id, choices.array[index]])))
  const [picks, setPicks] = useState<string[]>([])
  const chosen = choices.classes.find((item) => item.id === classId) ?? choices.classes[0]
  const background = choices.backgrounds.find((item) => item.id === backgroundId) ?? choices.backgrounds[0]
  const open = skillChoices(chosen.skills.from, background.skills)
  const report = (next: Partial<{ classId: string; speciesId: string; backgroundId: string; scores: Record<string, number>; picks: string[] }>) => {
    const build = { class_id: next.classId ?? classId, species_id: next.speciesId ?? speciesId, background_id: next.backgroundId ?? backgroundId, scores: next.scores ?? scores, skills: next.picks ?? picks }
    const count = choices.classes.find((item) => item.id === build.class_id)?.skills.count ?? 0
    onChange(arrayPlaced(build.scores, choices.array) && build.skills.length === count ? build : null)
  }
  const pickClass = (id: string) => { setClassId(id); setPicks([]); report({ classId: id, picks: [] }) }
  const pickBackground = (id: string) => { setBackgroundId(id); setPicks([]); report({ backgroundId: id, picks: [] }) }
  const place = (ability: string, value: number) => { const next = { ...scores, [ability]: value }; setScores(next); report({ scores: next }) }
  const toggle = (skill: string) => {
    const next = picks.includes(skill) ? picks.filter((item) => item !== skill) : [...picks, skill].slice(-chosen.skills.count)
    setPicks(next)
    report({ picks: next })
  }
  return (
    <fieldset className="story-build">
      <legend>Your 5E character</legend>
      <PackSelect label="Class" value={classId} items={choices.classes} onChange={pickClass} />
      <PackSelect label="Species" value={speciesId} items={choices.species} onChange={(id) => { setSpeciesId(id); report({ speciesId: id }) }} />
      <PackSelect label="Background" value={backgroundId} items={choices.backgrounds} onChange={pickBackground} />
      <p className="subtle">Place 15, 14, 13, 12, 10 and 8, one on each ability. {background.name} then adds +2 and +1 among {background.abilities.join(', ')}. {chosen.name}s lean on {chosen.primary}.</p>
      <div className="story-abilities">
        {choices.abilities.map((ability) => <label key={ability.id} className="field">{ability.name}
          <select value={scores[ability.id]} onChange={(event) => place(ability.id, Number(event.target.value))}>
            {choices.array.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>)}
      </div>
      {!arrayPlaced(scores, choices.array) && <p className="story-points over">Use each number once.</p>}
      <p className="subtle">Pick {chosen.skills.count} skills ({background.name} gives {background.skills.join(' and ')}).</p>
      <div className="story-skills">
        {open.map((skill) => <label key={skill} className="checkbox">
          <input type="checkbox" checked={picks.includes(skillId(skill))} onChange={() => toggle(skillId(skill))} />{skill}
        </label>)}
      </div>
      <p className="subtle story-attribution">{choices.attribution}</p>
    </fieldset>
  )
}

function PackSelect({ label, value, items, onChange }: { label: string; value: string; items: { id: string; name: string }[]; onChange: (id: string) => void }) {
  return (
    <label className="field">{label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </label>
  )
}

/** The start's optional choices, only those the player made. */
function given(choices: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(choices).filter(([, value]) => value))
}

function adultAge(years: number | null): boolean {
  return years === null || (years >= 18 && years <= 120)
}

/** MARVEL's stats bought from the pool of points (dungeon/campaign.py bought). */
function MarvelStats({ choices, stats, onChange }: { choices: StartChoices; stats: Record<string, number>; onChange: (stats: Record<string, number>) => void }) {
  const [min, max] = choices.range
  const left = pointsLeft(stats, choices.points)
  return <>
    <p className={left < 0 ? 'story-points over' : 'story-points'}>{pointsText(left, choices.points)}</p>
    <div className="story-stats">
      {choices.stat_names.map((stat) => (
        <Stepper key={stat} label={stat} value={stats[stat]} min={min} max={max} hint={choices.meanings[stat]}
          format={String} onChange={(value) => onChange({ ...stats, [stat]: value })} />
      ))}
    </div>
  </>
}
