import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import type { WorkspaceSettings } from '../../types'
import { Field } from '../../components/Fields'
import { Notice } from '../../components/Feedback'

const BUDGETS: [number, string][] = [[0, 'Automatic (90 seconds on this PC, 30 for an online model)'], [15, '15 seconds'],
  [30, '30 seconds'], [60, '1 minute'], [90, '90 seconds'], [120, '2 minutes'], [180, '3 minutes']]

/** Models > Turn speed (dungeon/pace.py): how long a story turn may take before its optional steps give way. */
export function TurnSpeed() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const [error, setError] = useState('')
  const save = async (turn_budget: number) => {
    setError('')
    try { client.setQueryData(SETTINGS_KEY, await api<WorkspaceSettings>('/settings', { turn_budget }, 'PUT')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (
    <section className="settings-section form-stack" aria-labelledby="turn-speed-heading">
      <div>
        <h2 id="turn-speed-heading">Turn speed</h2>
        <p className="subtle">The story streams as it is written, and the facts are noted after you can read it.</p>
      </div>
      <Field label="Time for each turn" hint="Past it, the polishing steps give way: the prose rewrite first, then the check against the record. Dice and the record are never skipped.">
        {(id, describedBy) => <select id={id} value={settings.data?.turn_budget ?? 0} disabled={!settings.data} aria-describedby={describedBy}
          onChange={(event) => void save(Number(event.target.value))}>
          {BUDGETS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>}
      </Field>
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}
