import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Sheet } from '../../types'
import { Stepper } from '../../components/NumberFields'
import { Notice } from '../../components/Feedback'
import { darkText } from './storyText'

const SHEET_KEY = ['story-sheet']

/** Your character's MARVEL stats (dungeon/sheet.py): each one rolls a bigger die as it grows, and one used under
 * pressure is marked to grow at the next rest (dungeon/growth.py); and the dark tracks they are on. */
export function StorySheet({ open }: { open?: boolean }) {
  const client = useQueryClient()
  const sheet = useQuery({ queryKey: SHEET_KEY, queryFn: () => api<Sheet>('/story/sheet') })
  const [error, setError] = useState('')
  if (!sheet.data) return null
  const [min, max] = sheet.data.range
  const growth = sheet.data.growth
  const save = async (stat: string, value: number) => {
    setError('')
    try { client.setQueryData(SHEET_KEY, await api<Sheet>('/story/sheet', { stats: { [stat]: value } }, 'PUT')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  return (
    <details className="story-sheet" open={open}>
      <summary>Your character</summary>
      <div className="story-stats">
        {sheet.data.stat_names.map((stat) => (
          <Stepper key={stat} label={growth?.marked.includes(stat) ? `${stat} •` : stat} value={sheet.data.stats[stat]} min={min} max={max}
            format={(value) => `${value} (d${sheet.data.dice[stat]})`} onChange={(value) => void save(stat, value)} />
        ))}
      </div>
      {!!growth?.marked.length && <p className="subtle">• Used under pressure: may grow at the next night's rest.</p>}
      {growth?.dark.map((track) => <p key={track.id}><strong>{darkText(track)}</strong>{track.changes.map((change) => <span key={change} className="subtle"> {change}</span>)}</p>)}
      {error && <Notice tone="error">{error}</Notice>}
    </details>
  )
}
