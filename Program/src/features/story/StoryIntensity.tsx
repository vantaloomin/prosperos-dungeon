import { useState } from 'react'
import { api } from '../../api'
import type { IntensityPreset, StoryIntensity as Intensity } from '../../types'
import { Field } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { intensityChoices } from './storyText'

/** How far the story goes on the page (dungeon/story.py intensity): the world's preset, or the player's, at any time. */
export function StoryIntensity({ intensity, onSaved }: { intensity: Intensity; onSaved: () => void }) {
  const [error, setError] = useState('')
  const save = async (value: IntensityPreset) => {
    setError('')
    try { await api('/settings', { intensity: value }, 'PUT'); onSaved() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (<>
    <Field label="How far the story goes" hint="Violence, sex, horror, cruelty and drugs on the page. Change it whenever you like; the next line follows it.">
      {(id, describedBy) => <select id={id} value={intensity.chosen} aria-describedby={describedBy}
        onChange={(event) => void save(event.target.value as IntensityPreset)}>
        {intensityChoices(intensity.world).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    {error && <Notice tone="error">{error}</Notice>}
  </>)
}
