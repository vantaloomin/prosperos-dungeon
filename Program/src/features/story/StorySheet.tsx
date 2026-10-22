import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { BrpSheet, IronswornSheet, MarvelSheet, Sheet, SheetGrowth, Srd52Sheet, Srd52Spells } from '../../types'
import { Stepper } from '../../components/NumberFields'
import { Notice } from '../../components/Feedback'
import { abilityLine, darkText, signed, spellLine, xpLine } from './storyText'

const SHEET_KEY = ['story-sheet']

/** Your character in the campaign's ruleset (dungeon/sheet.py): MARVEL's stats, each rolling a bigger die as it
 * grows, one used under pressure marked to grow at the next rest (dungeon/growth.py); or a 5E sheet. And the dark
 * tracks they are on. */
export function StorySheet({ open }: { open?: boolean }) {
  const sheet = useQuery({ queryKey: SHEET_KEY, queryFn: () => api<Sheet>('/story/sheet') })
  if (!sheet.data) return null
  return (
    <details className="story-sheet" open={open}>
      <summary>Your character</summary>
      <Rules sheet={sheet.data} />
      <Dark growth={sheet.data.growth} />
    </details>
  )
}

function Rules({ sheet }: { sheet: Sheet }) {
  if (sheet.ruleset === 'srd52') return <Srd52 sheet={sheet} />
  if (sheet.ruleset === 'ironsworn') return <Ironsworn sheet={sheet} />
  if (sheet.ruleset === 'brp') return <Percentile sheet={sheet} />
  return <Marvel sheet={sheet} />
}

/** A Percentile sheet (dungeon/rules/brp.py): set when the character was made; skills grow by experience. */
function Percentile({ sheet }: { sheet: BrpSheet }) {
  return <>
    <p>{sheet.names.profession}, {sheet.names.personality.toLowerCase()}</p>
    <p>{Object.entries(sheet.characteristics).map(([stat, value]) => `${stat.toUpperCase()} ${value}`).join(' · ')}</p>
    <p>Hit points {Math.max(0, sheet.hp)} of {sheet.max_hp} (major wound {sheet.major_wound}) · Damage {sheet.damage_modifier} · Armour {sheet.armor_name} ({sheet.armor_value})</p>
    <p className="subtle">{Object.entries(sheet.rolls).map(([roll, value]) => `${roll} ${value}%`).join(' · ')}</p>
    {!!sheet.major_wounds.length && <p className="subtle">{sheet.major_wounds.map((wound) => wound.text).join(' ')}</p>}
    <details>
      <summary>Skills</summary>
      <p>{sheet.skill_list.filter((skill) => skill.value > 0).map((skill) => `${skill.name} ${skill.value}%${skill.checked ? ' •' : ''}`).join(' · ')}</p>
      <p className="subtle">• an experience check, rolled after a night's rest.</p>
    </details>
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

/** An Ironsworn sheet (dungeon/rules/ironsworn.py): set when the character was made, so it only reads. */
function Ironsworn({ sheet }: { sheet: IronswornSheet }) {
  return <>
    <p>{Object.entries(sheet.stats).map(([stat, value]) => `${stat} ${value}`).join(' · ')}</p>
    <p>Health {sheet.health} · Spirit {sheet.spirit} · Supply {sheet.supply} · Momentum {signed(sheet.momentum)} (max {sheet.momentum_max}, reset {sheet.momentum_reset}) · Experience {sheet.xp}</p>
    {!!sheet.debilities.length && <p className="subtle">{sheet.debilities.join(', ')}</p>}
    <details>
      <summary>Assets</summary>
      {sheet.asset_list.map((asset) => <p key={asset.id}><strong>{asset.name}</strong> <span className="subtle">({asset.category})</span> {asset.abilities.join(' ')}</p>)}
    </details>
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

function Marvel({ sheet }: { sheet: MarvelSheet }) {
  const client = useQueryClient()
  const [error, setError] = useState('')
  const [min, max] = sheet.range
  const growth = sheet.growth
  const save = async (stat: string, value: number) => {
    setError('')
    try { client.setQueryData(SHEET_KEY, await api<Sheet>('/story/sheet', { stats: { [stat]: value } }, 'PUT')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  return <>
    <div className="story-stats">
      {sheet.stat_names.map((stat) => (
        <Stepper key={stat} label={growth?.marked.includes(stat) ? `${stat} •` : stat} value={sheet.stats[stat]} min={min} max={max}
          format={(value) => `${value} (d${sheet.dice[stat]})`} onChange={(value) => void save(stat, value)} />
      ))}
    </div>
    {!!growth?.marked.length && <p className="subtle">• Used under pressure: may grow at the next night's rest.</p>}
    {error && <Notice tone="error">{error}</Notice>}
  </>
}

/** A 5E sheet (dungeon/rules/srd52.py): set when the character was made, so it only reads. */
function Srd52({ sheet }: { sheet: Srd52Sheet }) {
  const skills = Object.entries(sheet.skill_bonuses)
  return <>
    <p><strong>Level {sheet.level} {sheet.names.species} {sheet.names.class}</strong> <span className="subtle">({sheet.names.background})</span></p>
    <p className="subtle">{xpLine(sheet.level, sheet.xp, sheet.next_xp)}</p>
    <p>Hit points {sheet.hp} of {sheet.max_hp} · Armor Class {sheet.ac} · Speed {sheet.speed} ft. · Proficiency {signed(sheet.proficiency)}</p>
    <ul className="story-abilities" aria-label="Abilities">
      {Object.entries(sheet.abilities).map(([ability, score]) => <li key={ability}>{abilityLine(ability, score, sheet.modifiers[ability], sheet.saves.includes(ability))}</li>)}
    </ul>
    <details>
      <summary>Skills</summary>
      <ul className="story-skills">
        {skills.map(([id, skill]) => <li key={id} className={skill.proficient ? 'proficient' : undefined}>{skill.name} {signed(skill.bonus)}{skill.proficient ? ' •' : ''}</li>)}
      </ul>
      <p className="subtle">• Proficient.</p>
    </details>
    {!!sheet.features?.length && <details><summary>Features</summary><p>{sheet.features.join(', ')}</p></details>}
    {sheet.spell_list && <Spells spells={sheet.spell_list} />}
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

function Spells({ spells }: { spells: Srd52Spells }) {
  return (
    <details>
      <summary>Spells</summary>
      <p>{spellLine(spells)}</p>
      {!!spells.cantrips.length && <p>Cantrips: {spells.cantrips.join(', ')}</p>}
      <p>Prepared: {spells.prepared.map((spell) => `${spell.name} (${spell.level})`).join(', ')}</p>
      <p className="subtle">Name a spell in your line to cast it.</p>
    </details>
  )
}

function Dark({ growth }: { growth?: SheetGrowth }) {
  return <>{growth?.dark.map((track) => <p key={track.id}><strong>{darkText(track)}</strong>{track.changes.map((change) => <span key={change} className="subtle"> {change}</span>)}</p>)}</>
}
