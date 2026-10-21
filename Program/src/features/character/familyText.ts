import type { KidsView, Kid } from '../../types'
import { firstName } from './panelText.ts'

/** The first choice of each picker: the app's own pick, named. */
export function appPick(label: string): string {
  return `Let the app decide (${label})`
}

export const KIDS_KEY = ['kids']

/** "Leo, 7, son" or "Ivy, 7 months old, daughter": one of their own children on the Family panel. */
export function kidLine(kid: Kid): string {
  const age = kid.age_text === 'a newborn' ? 'newborn' : kid.age_text
  return `${kid.name}, ${age}, ${kid.relation}`
}

/** Where their kids came from, under the list. */
export function kidsHint(view: KidsView, name: string): string {
  const who = firstName(name)
  if (view.how === 'town') return `${who} had them while living in town, before they were a companion.`
  if (view.how === 'seeded') return `Picked by the app for ${who}. Take a child out of their life if they shouldn't be there.`
  return `Read from ${who}'s description. Take a child out of their life if they shouldn't be there.`
}

/** Under "Where the kids live": who decided it, the arrangement spelled out, and the other parent. */
export function whereHint(view: KidsView, name: string): string {
  const who = firstName(name)
  const other = view.other ? ` ${firstName(view.other.name)}, their other parent, is ${who}'s ${view.other.role}.` : ''
  const detail = view.detail ? `: ${view.detail}.` : '.'
  if (view.pattern_how === 'set') return `You set this${detail}${other}`
  if (view.pattern_how === 'fixed') return `Read from ${who}'s description${detail}${other}`
  return `Picked by the app${detail}${other}`
}

/** The first choice of "Where the kids live": the description's arrangement or the app's pick, named. */
export function wherePick(view: KidsView, name: string, label: string): string {
  if (view.pattern_how === 'fixed') return `From ${firstName(name)}'s description (${label})`
  return appPick(view.pattern_how === 'set' ? 'what fits them' : label)
}

/** "Leo", "Leo and Mia", "Leo, Mia and Sam". */
export function kidNames(view: KidsView): string {
  const names = (view.kids ?? []).map((kid) => kid.name)
  return names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}
