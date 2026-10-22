import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { MarvelSheet, Sheet, SheetGrowth, Srd52Sheet } from '../../types'
import { Stepper } from '../../components/NumberFields'
import { Notice } from '../../components/Feedback'
import { abilityLine, darkText, signed } from './storyText'

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
      {sheet.data.ruleset === 'srd52' ? <Srd52 sheet={sheet.data} /> : <Marvel sheet={sheet.data} />}
      <Dark growth={sheet.data.growth} />
    </details>
  )
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
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

function Dark({ growth }: { growth?: SheetGrowth }) {
  return <>{growth?.dark.map((track) => <p key={track.id}><strong>{darkText(track)}</strong>{track.changes.map((change) => <span key={change} className="subtle"> {change}</span>)}</p>)}</>
}
