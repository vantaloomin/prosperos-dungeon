import { useState } from 'react'
import type { DefeatRule, DramaLevel, IntensityPreset, StoryIntensity as Intensity } from '../../types'
import { Field, Toggle } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { dramaChoices, intensityChoices } from './storyText'
import { useTable } from './table'

/** How far the story goes on the page (dungeon/story.py intensity) and how eventful it is (dungeon/happenings.py):
 * the world's own, or the player's, at any time; and whether off-page beats are shown (dungeon/beats.py). This
 * campaign's rules, kept at the Table (./table.ts). */
export function StoryIntensity({ intensity, onSaved }: { intensity: Intensity; onSaved: () => void }) {
  const { save: keep } = useTable()
  const [error, setError] = useState('')
  const save = async (change: { intensity: IntensityPreset } | { drama: DramaLevel } | { cutaways: boolean } | { defeat: DefeatRule }) => {
    setError('')
    try { await keep(change); onSaved() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (<>
    <Field label="How far the story goes" hint="Violence, sex, horror, cruelty and drugs on the page. Change it whenever you like; the next line follows it.">
      {(id, describedBy) => <select id={id} value={intensity.chosen} aria-describedby={describedBy}
        onChange={(event) => void save({ intensity: event.target.value as IntensityPreset })}>
        {intensityChoices(intensity.world).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    <Field label="How eventful" hint="How often the world throws something at you: news, trouble, a stranger at the fire. It never changes the dice.">
      {(id, describedBy) => <select id={id} value={intensity.drama_chosen ?? 'world'} aria-describedby={describedBy}
        onChange={(event) => void save({ drama: event.target.value as DramaLevel })}>
        {dramaChoices(intensity.drama_world ?? 'uneasy').map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    <Toggle label="Meanwhile cutaways" hint="Short scenes of what happens to the people you know while you are elsewhere. Your character still only learns it when word reaches them."
      checked={Boolean(intensity.cutaways)} onChange={(checked) => void save({ cutaways: checked })} />
    {intensity.ruleset === 'srd52' && <Toggle label="Foes decide a defeat" hint="Off: at 0 hit points the death saves decide, as written. On: only foes out to kill bring the death saves; others take what they came for, a prisoner, a purse or a beaten stranger thrown out."
      checked={intensity.defeat === 'by_aim'} onChange={(checked) => void save({ defeat: checked ? 'by_aim' : 'as_written' })} />}
    {error && <Notice tone="error">{error}</Notice>}
  </>)
}
