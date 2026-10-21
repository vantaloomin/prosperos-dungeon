import type { CirclePerson } from '../../types'

/** "close friend · she/her · 40" or "sister · married, born Smith · she/her · 31": how they relate to the companion, then what is known about them. */
export function personFacts(person: CirclePerson): string {
  const role = person.closeness && person.closeness !== 'close' ? `${person.role} (${person.closeness})` : person.role
  const married = person.married ? (person.birth_family ? `married, born ${person.birth_family}` : 'married') : null
  return [role, married, person.pronouns, person.age ? String(person.age) : null].filter(Boolean).join(' · ')
}

/** Where they are in their week, without implying the companion is with them. */
export function personNow(person: CirclePerson): string {
  if (person.local === false) return 'Lives out of town'
  if (!person.now) return 'Free right now'
  return person.now.kind === 'sleep' ? 'Asleep right now' : `Right now: ${person.now.label}`
}

export function personWork(person: CirclePerson): string | null {
  if (!person.career) return null
  return person.employer ? `${person.career}, ${person.employer}` : person.career
}

/** The full name when known (it tells apart two people with one given name), unless they were renamed since. */
export function displayName(person: CirclePerson): string {
  return person.full_name?.startsWith(`${person.name} `) ? person.full_name : person.name
}

/** Parents in the circle: married, divorced, or separated in an older city (dungeon/life/circle.py `tie`). */
const COUPLED: Record<string, string> = { married: 'Married to', divorced: 'Divorced from', separated: 'Separated from' }

/** "Married to Rui. Knows Ana (family), Dev (coworkers)": who they know inside the circle. */
export function personTies(person: CirclePerson): string | null {
  const known = person.knows ?? []
  const partners = known.filter((item) => Object.hasOwn(COUPLED, item.how))
    .map((item) => `${COUPLED[item.how]} ${item.name}.`)
  const others = known.filter((item) => !Object.hasOwn(COUPLED, item.how)).map((item) => `${item.name} (${item.how})`)
  const text = [...partners, ...(others.length ? [`Knows ${others.join(', ')}.`] : [])].join(' ')
  return text || null
}
