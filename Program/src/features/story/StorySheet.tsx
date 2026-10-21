import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Sheet } from '../../types'
import { Stepper } from '../../components/NumberFields'
import { Notice } from '../../components/Feedback'

const SHEET_KEY = ['story-sheet']

/** Your character's MARVEL stats (dungeon/sheet.py): each one rolls a bigger die as it grows. */
export function StorySheet() {
  const client = useQueryClient()
  const sheet = useQuery({ queryKey: SHEET_KEY, queryFn: () => api<Sheet>('/story/sheet') })
  const [error, setError] = useState('')
  if (!sheet.data) return null
  const [min, max] = sheet.data.range
  const save = async (stat: string, value: number) => {
    setError('')
    try { client.setQueryData(SHEET_KEY, await api<Sheet>('/story/sheet', { stats: { [stat]: value } }, 'PUT')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  return (
    <details className="story-sheet">
      <summary>Your character</summary>
      <div className="story-stats">
        {sheet.data.stat_names.map((stat) => (
          <Stepper key={stat} label={stat} value={sheet.data.stats[stat]} min={min} max={max}
            format={(value) => `${value} (d${sheet.data.dice[stat]})`} onChange={(value) => void save(stat, value)} />
        ))}
      </div>
      {error && <Notice tone="error">{error}</Notice>}
    </details>
  )
}
