import type { StoryFaction } from '../../types'

/** The factions your character knows of (dungeon/factions.py) and how you stand with each. */
export function StoryPowers({ factions, open }: { factions: StoryFaction[]; open?: boolean }) {
  if (!factions.length) return null
  return (
    <details className="story-people" open={open}>
      <summary>Powers ({factions.length})</summary>
      <ul>
        {factions.map((faction) => <li key={faction.id}>
          <p><strong>{faction.name}</strong> <span className="subtle">· you are {faction.standing} to them</span></p>
          <p className="subtle">{faction.summary}</p>
        </li>)}
      </ul>
    </details>
  )
}
