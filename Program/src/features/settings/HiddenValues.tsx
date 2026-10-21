import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import type { WorkspaceSettings } from '../../types'
import { Toggle } from '../../components/Fields'
import { Notice } from '../../components/Feedback'

type Flag = 'adult_side' | 'show_odds' | 'show_adult_side'

function useFlags() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const [error, setError] = useState('')
  const save = async (change: Partial<Record<Flag, boolean>>) => {
    setError('')
    try {
      client.setQueryData(SETTINGS_KEY, await api<WorkspaceSettings>('/settings', change, 'PUT'))
      // The story carries its rolls only while the dice are shown.
      if ('show_odds' in change) await client.invalidateQueries({ queryKey: ['story'] })
    }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return { settings: settings.data, save, error }
}

/** World > Adult side of life (dungeon/world/intimacy.py): off until the user turns it on. */
export function AdultSideSettings() {
  const { settings, save, error } = useFlags()
  return (
    <section className="settings-section form-stack" aria-labelledby="adult-side-heading">
      <div>
        <h2 id="adult-side-heading">Adult side of life</h2>
        <p className="subtle">Real people have a love life and desires of their own. Off until you turn it on.</p>
      </div>
      <Toggle label="Give adults an adult side" checked={settings?.adult_side === true} disabled={!settings} onChange={(checked) => void save({ adult_side: checked })}
        hint="Every adult townsperson gets who they're drawn to, how adventurous they are, their drive and a few things they're into, rolled by the app. Adults only: nobody under 18 ever gets one." />
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}

/** World > Hidden values: what shapes the story but stays unseen unless the user turns it on. */
export function HiddenValues() {
  const { settings, save, error } = useFlags()
  return (
    <section className="settings-section form-stack" aria-labelledby="hidden-values-heading">
      <div>
        <h2 id="hidden-values-heading">Hidden values</h2>
        <p className="subtle">Some things stay behind the curtain: you notice them from how the story goes, not from a label.</p>
      </div>
      <Toggle label="Show the dice" checked={settings?.show_odds === true} disabled={!settings} onChange={(checked) => void save({ show_odds: checked })}
        hint="Each roll under your line: the stat, the die, the difficulty and how it landed. Off, you feel the dice only through the story." />
      {settings?.adult_side && (
        <Toggle label="Show townsfolk's adult side" checked={settings.show_adult_side === true} onChange={(checked) => void save({ show_adult_side: checked })}
          hint="Who each person is drawn to, how adventurous they are and what they're into." />
      )}
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}
