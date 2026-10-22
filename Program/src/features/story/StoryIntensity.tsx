import { useState } from 'react'
import { api } from '../../api'
import type { DramaLevel, IntensityPreset, StoryIntensity as Intensity } from '../../types'
import { Field } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { dramaChoices, intensityChoices } from './storyText'

/** How far the story goes on the page (dungeon/story.py intensity) and how eventful it is (dungeon/happenings.py):
 * the world's own, or the player's, at any time. */
export function StoryIntensity({ intensity, onSaved }: { intensity: Intensity; onSaved: () => void }) {
  const [error, setError] = useState('')
  const save = async (change: { intensity: IntensityPreset } | { drama: DramaLevel }) => {
    setError('')
    try { await api('/settings', change, 'PUT'); onSaved() }
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
    {error && <Notice tone="error">{error}</Notice>}
  </>)
}
