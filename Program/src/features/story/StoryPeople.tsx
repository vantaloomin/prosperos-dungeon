import type { StoryPerson } from '../../types'
import { personLine } from './storyText'

interface Props { people: StoryPerson[]; onFind: (key: string) => void }

/** The people the user has met in the story. */
export function StoryPeople({ people, onFind }: Props) {
  if (!people.length) return null
  return (
    <details className="story-people">
      <summary>People you&apos;ve met ({people.length})</summary>
      <ul>
        {people.map((person) => (
          <li key={person.key}>
            <p><strong>{person.name}</strong> <span className="subtle">{person.role}, {person.city}</span></p>
            <p className="subtle">{personLine(person)}</p>
            {person.feelings && <p className="subtle">{person.feelings}</p>}
            {person.notes.length > 0 && <p className="story-note">{person.notes[person.notes.length - 1]}</p>}
            <div className="form-actions">
              {person.place && <button type="button" className="text-button" onClick={() => onFind(person.key)}>Go to {person.name.split(' ')[0]}</button>}
            </div>
          </li>))}
      </ul>
    </details>
  )
}
