import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { KidsView } from '../../types'
import { ErrorNotice } from '../../components/ErrorNotice'
import { KIDS_KEY } from './familyText'
import { Kids, KidsUndo, type Removed } from './Kids'

/** The kids they already have (dungeon/life/kids.py). The app picks where they live; the user can change it. */
export function Family({ name }: { name: string }) {
  const kids = useQuery({ queryKey: KIDS_KEY, queryFn: () => api<KidsView>('/life/steps/kids') })
  const [removed, setRemoved] = useState<Removed>(null)
  if (kids.error) return <ErrorNotice error={kids.error} />
  const theirs = kids.data?.shown ? kids.data : null
  if (!theirs && !removed) return null
  return (
    <section id="family" className="home-panel steps-panel family-panel" aria-labelledby="family-heading">
      <h2 id="family-heading">Family</h2>
      {theirs ? <Kids view={theirs} name={name} removed={removed} setRemoved={setRemoved} />
        : <KidsUndo removed={removed} setRemoved={setRemoved} />}
    </section>
  )
}
