import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { SETTINGS_KEY, pcTimezone, timezones, useWorkspaceSettings } from '../../workspace'
import { api } from '../../api'
import type { WorkspaceSettings as Settings } from '../../types'
import { Notice } from '../../components/Feedback'
import { TextInput } from '../../components/Fields'

type Save = (change: Partial<Settings>) => Promise<boolean>

/**
 * The workspace settings and a way to change them, shared by the sections on several Settings tabs.
 * Toggles show the new state at once and fall back to the saved state if the change is refused.
 */
function useWorkspace() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<Partial<Settings>>({})
  const save: Save = async (change) => {
    setPending((current) => ({ ...current, ...change }))
    try {
      const saved = await api<Settings>('/settings', change, 'PUT')
      // Holding the saved values locally avoids a flicker before the shared cache re-renders. Only
      // the changed ones: other tabs' sections save the rest, and a stale copy here would hide them.
      setPending((current) => ({ ...current, ...pick(saved, change) }))
      client.setQueryData(SETTINGS_KEY, saved)
      setError(null)
      return true
    } catch (failure) {
      setPending({})
      setError(failure instanceof Error ? failure.message : 'That setting was not saved.')
      return false
    }
  }
  const data = settings.data ? { ...settings.data, ...pending } : null
  const problem = error ?? (settings.isError ? settings.error.message : null)
  return { data, save, setError, setPending, problem }
}

function pick(saved: Settings, change: Partial<Settings>): Partial<Settings> {
  return Object.fromEntries(Object.keys(change).filter((key) => key in saved).map((key) => [key, saved[key as keyof Settings]]))
}

function SectionError({ problem }: { problem: string | null }) {
  return problem ? <Notice tone="error">{problem}</Notice> : null
}

export function TimezoneSettings() {
  const { data, save, problem } = useWorkspace()
  if (!data) return <SectionError problem={problem} />
  return <TimezoneForm data={data} save={save} problem={problem} />
}

function TimezoneForm({ data, save, problem }: { data: Settings; save: Save; problem: string | null }) {
  const [zone, setZone] = useState<string | null>(null)
  const pc = pcTimezone(data)
  const edited = zone !== null && zone !== data.user_timezone
  const offerPc = !!pc && (zone !== null || `${data.user_timezone_source}:${data.user_timezone}` !== `pc:${pc}`)
  const savedZone = (change: Partial<Settings>) => void save(change).then((saved) => {
    if (saved) setZone(null)
  })
  const hint = ZONE_HINTS[data.user_timezone_source]
  return (
    <section className="settings-section form-stack" aria-labelledby="time-heading">
      <h2 id="time-heading">Your time</h2>
      <SectionError problem={problem} />
      <TextInput label="Your timezone" value={zone ?? data.user_timezone} onChange={setZone} list="settings-timezones" maxLength={64} hint={hint} />
      <datalist id="settings-timezones">{timezones().map((item) => <option key={item} value={item} />)}</datalist>
      {pc && <p className="subtle">This PC's timezone: {pc}</p>}
      {(edited || offerPc) && (
        <div className="form-actions">
          {edited && <button type="button" className="button primary" onClick={() => savedZone({ user_timezone: zone!, user_timezone_source: 'chosen' })}>Save time zone</button>}
          {offerPc && <button type="button" className="button" onClick={() => savedZone({ user_timezone: pc!, user_timezone_source: 'pc' })}>Use this PC's time zone</button>}
        </div>
      )}
    </section>
  )
}

const ZONE_USE = 'Used for dates and what time it is for you.'
const ZONE_HINTS: Record<Settings['user_timezone_source'], string> = {
  pc: `Following this PC's timezone. ${ZONE_USE}`,
  chosen: `Set by you, so it stays put if this PC's timezone changes. ${ZONE_USE}`,
  default: ZONE_USE,
}
