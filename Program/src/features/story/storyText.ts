import type { Gear, JournalEntry, JournalQuest, Premade, StoryBranch, StoryPerson, StoryPlace, StoryRoll, StoryScene, StoryStart, StoryFight } from '../../types'

/** "Tuesday, 9:40 am" from the scene's local time, which is the city's own clock with no offset. */
export function sceneTime(localTime: string): string {
  const [day, clock] = localTime.split('T')
  const [year, month, date] = day.split('-').map(Number)
  const [hour, minute] = clock.split(':').map(Number)
  const weekday = new Date(Date.UTC(year, month - 1, date)).toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' })
  return `${weekday}, ${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour < 12 ? 'am' : 'pm'}`
}

const COUNTS = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']

const IRREGULAR: Record<string, string> = { man: 'men', woman: 'women', person: 'people', child: 'children' }
// Words that end the role and start what follows it: "a head chef| at Joe's", "a neighbor| waiting for the bus".
const AFTER_ROLE = /^(.+?)((?: (?:from|at|of|in|on|with|near|by|for|who|that|behind|outside|inside|[a-z]+ing)\b|,).*)?$/

function plural(word: string): string {
  if (IRREGULAR[word]) return IRREGULAR[word]
  if (/(s|sh|ch|x|z)$/.test(word)) return `${word}es`
  return /[^aeiou]y$/.test(word) ? `${word.slice(0, -1)}ies` : `${word}s`
}

/** "head chef at Joe's" -> "head chefs at Joe's": the role's last word, its head noun, takes the plural. */
function pluralRole(phrase: string): string {
  const [, role, rest = ''] = AFTER_ROLE.exec(phrase) ?? [phrase, phrase, '']
  const words = role.split(' ')
  return [...words.slice(0, -1), plural(words[words.length - 1])].join(' ') + rest
}

/** Unnamed people who read the same are counted: three of "a local from Canton" are "three locals from Canton". */
export function grouped(around: string[]): string[] {
  const counts = new Map<string, number>()
  for (const who of around) counts.set(who, (counts.get(who) ?? 0) + 1)
  return [...counts.entries()].flatMap(([who, count]) => {
    const unnamed = /^(?:an?|the) (.+)$/.exec(who)
    if (count === 1) return [who]
    if (!unnamed) return Array<string>(count).fill(who)
    return [`${COUNTS[count] ?? count} ${pluralRole(unnamed[1])}`]
  })
}

/** "Nobody you would notice is here.", "The barista is here.", "A regular and two neighbors are here." */
export function aroundText(around: string[]): string {
  if (!around.length) return 'Nobody you would notice is here.'
  const names = grouped(around).map((who, index) => index ? who : who[0].toUpperCase() + who.slice(1))
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
  return `${list} ${around.length === 1 ? 'is' : 'are'} here.`
}

/** The city's places by neighborhood, for the place picker. */
export function placeGroups(places: StoryPlace[]): [string, StoryPlace[]][] {
  const groups = new Map<string, StoryPlace[]>()
  for (const place of places) groups.set(place.neighborhood, [...(groups.get(place.neighborhood) ?? []), place])
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
}

export function whereText(scene: StoryScene): string {
  return `${scene.place.name}, ${scene.place.neighborhood}, ${scene.city.name}`
}

/** "Inside: the back patio, the bar seats" */
export function spotsText(spots: string[]): string {
  return `Inside: ${spots.join(', ')}`
}

/** "Met once · now working as the barista at The Daily Grind" */
export function personLine(person: StoryPerson): string {
  const times = person.meetings === 1 ? 'once' : person.meetings === 2 ? 'twice' : `${person.meetings} times`
  const where = person.place && !person.doing.includes(person.place.name) ? ` at ${person.place.name}` : ''
  return `Met ${times} · now ${person.doing}${where}`
}

/** "Allure d8: 62 + 5, hard (-10) = 57, Success at a cost". */
export function rollText(roll: StoryRoll): string {
  const die = roll.die ? ` d${roll.die}` : ''
  const sum = roll.die ? `${roll.natural} + ${roll.bonus}` : `${roll.natural}`
  const shift = roll.shift ? `, ${roll.difficulty.replace('_', ' ')} (${roll.shift > 0 ? '-' : '+'}${Math.abs(roll.shift)})` : ''
  return `${roll.stat}${die}: ${sum}${shift} = ${roll.total}, ${roll.label}`
}

/** "a woman, 41" under a premade's name. */
export function premadeLine(premade: Pick<Premade, 'gender' | 'age'>): string {
  const gender = premade.gender === 'nonbinary' ? 'nonbinary' : premade.gender ? `a ${premade.gender}` : ''
  return [gender, premade.age ? String(premade.age) : ''].filter(Boolean).join(', ')
}

/** A made character starts with every stat as even as the points allow. */
export function startingStats(start: Pick<StoryStart, 'stat_names' | 'points' | 'range'>): Record<string, number> {
  const even = Math.min(start.range[1], Math.max(start.range[0], Math.floor(start.points / start.stat_names.length)))
  return Object.fromEntries(start.stat_names.map((stat) => [stat, even]))
}

/** "3 points left of 60", or how far over the pool the stats are. */
export function pointsText(left: number, points: number): string {
  const count = Math.abs(left)
  return `${count} ${count === 1 ? 'point' : 'points'} ${left < 0 ? 'over' : 'left'} of ${points}`
}

/** The points still to spend; below zero when the stats cost more than the pool. */
export function pointsLeft(stats: Record<string, number>, points: number): number {
  return points - Object.values(stats).reduce((sum, value) => sum + value, 0)
}

/** "3 turns, last played Tue 21 Oct" for a branch the player is not in. */
export function branchLine(branch: Pick<StoryBranch, 'turns' | 'last_at'>): string {
  const turns = `${branch.turns} ${branch.turns === 1 ? 'turn' : 'turns'}`
  if (!branch.last_at) return turns
  const day = new Date(branch.last_at)
  return `${turns}, last played ${day.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}`
}

const KINDS: Record<string, string> = { death: 'Death', item: 'Item', wound: 'Wound', promise: 'Promise', location: 'Place', secret: 'Secret', relationship: 'Relationship', fact: 'Fact' }

/** "Wound · you", and whether the character only believes it. */
export function journalKind(entry: Pick<JournalEntry, 'kind' | 'subject' | 'truth'>): string {
  return `${KINDS[entry.kind] ?? 'Fact'} · ${entry.subject}${entry.truth === 'belief' ? ' (you believe)' : ''}`
}

const QUEST_ENDS: Record<string, string> = { done: 'Done', failed: 'Failed', missed: 'Too late' }

/** A quest's state in the journal: the story time left while it is open, else how it ended. */
export function questState(quest: Pick<JournalQuest, 'status' | 'left'>): string {
  if (quest.status !== 'open') return QUEST_ENDS[quest.status] ?? 'Over'
  return quest.left ? `Underway · ${quest.left}` : 'Underway'
}

/** "3.40 cr.", from hundredths of the currency. */
export function moneyText(hundredths: number, currency: Gear['currency']): string {
  return `${(hundredths / 100).toFixed(2)} ${currency.symbol || currency.name || ''}`.trim()
}

/** "Rope, fifty feet × 2". */
export function gearLine(item: { name: string; qty: number }): string {
  return item.qty > 1 ? `${item.name} × ${item.qty}` : item.name
}

/** "6.35 of 13 slots". */
export function slotsText(slots: Gear['slots']): string {
  const round = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, '')
  return `${round(slots.used)} of ${round(slots.max)} slots`
}

/** "You are hurt. Fighting: the bandit (hurt), the lookout (broken)." or '' when unhurt and not fighting. */
export function fightText(fight: StoryFight): string {
  if (fight.dead) return 'Your character is dead. Go back to an earlier line to play on.'
  const condition = fight.condition === 'unhurt' ? '' : `You are ${fight.condition}.`
  const foes = fight.fight?.foes.map((foe) => `${foe.name} (${foe.state}${foe.wound === null ? '' : `, wound ${foe.wound} of 5`})`).join(', ')
  return [condition, foes ? `Fighting: ${foes}.` : ''].filter(Boolean).join(' ')
}
