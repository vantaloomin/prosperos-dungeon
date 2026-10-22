import assert from 'node:assert/strict'
import { test } from 'node:test'
import { actionLine, aroundText, diceFaces, diceNotation, tumbleFace, bandSpans, branchLine, journeyTo, markerAt, nearMiss, NO_TURN, turnAfter, reworded, sentences, fightText, haggleText, paceText, intensityChoices, dramaChoices, gearLine, journalKind, moneyText, questState, slotsText, personLine, placeGroups, pointsLeft, pointsText, premadeLine, rollText, sceneTime, startingStats, tierText, darkText, threadKind } from '../../src/features/story/storyText.ts'

test('the scene time is the city clock as written', () => {
  assert.equal(sceneTime('2026-10-06T09:05'), 'Tuesday, 9:05 am')
  assert.equal(sceneTime('2026-10-06T00:30'), 'Tuesday, 12:30 am')
  assert.equal(sceneTime('2026-10-06T21:40'), 'Tuesday, 9:40 pm')
})

test('who is around reads as a sentence', () => {
  assert.equal(aroundText([]), 'Nobody you would notice is here.')
  assert.equal(aroundText(['the barista']), 'The barista is here.')
  assert.equal(aroundText(['the barista', 'a regular', 'a neighbor']), 'The barista, a regular and a neighbor are here.')
})

test('unnamed people who read the same are counted, not repeated', () => {
  const local = (hood: string) => `a local from ${hood}`
  assert.equal(aroundText(['the barista', local('Little Italy'), local('Little Italy'), local('Harbor East'), local('Little Italy'), local('Fells Point')]),
    'The barista, three locals from Little Italy, a local from Harbor East and a local from Fells Point are here.')
  assert.equal(aroundText([local('Canton'), local('Canton')]), 'Two locals from Canton are here.')
  assert.equal(aroundText(['a neighbor waiting for the bus', 'a neighbor waiting for the bus']), 'Two neighbors waiting for the bus are here.')
  assert.equal(aroundText(['the barista', 'the barista', 'the waitress', 'the waitress']), 'Two baristas and two waitresses are here.')
  assert.equal(aroundText(['Dana, the barista', 'Dana, the barista']), 'Dana, the barista and Dana, the barista are here.')
  // A role of several words takes the plural on its head noun, its last word.
  assert.equal(aroundText(["a head chef at Joe's", "a head chef at Joe's"]), "Two head chefs at Joe's are here.")
  assert.equal(aroundText(['a line cook', 'a line cook', 'a delivery man', 'a delivery man']), 'Two line cooks and two delivery men are here.')
})

test('places are grouped by neighborhood', () => {
  const place = (id: string, neighborhood: string) => ({ id, name: id, kind: 'cafe', neighborhood })
  assert.deepEqual(placeGroups([place('b', 'Canton'), place('a', 'Fells Point'), place('c', 'Canton')]).map(([hood, items]) => [hood, items.map((item) => item.id)]),
    [['Canton', ['b', 'c']], ['Fells Point', ['a']]])
})

test('a person met says how often and where they are now', () => {
  const person = { key: 'k', name: 'Dana Kim', role: 'barista', city: 'Baltimore', meetings: 3, last_met_at: '', notes: [],
    doing: 'working as the barista', place: { id: 'p', name: 'The Daily Grind', city_id: 'baltimore' }, feelings: '' }
  assert.equal(personLine(person), 'Met 3 times · now working as the barista at The Daily Grind')
  assert.equal(personLine({ ...person, meetings: 1, doing: 'at home', place: null }), 'Met once · now at home')
  assert.equal(personLine({ ...person, doing: 'at their usual spot at The Daily Grind' }), 'Met 3 times · now at their usual spot at The Daily Grind')
})

test('a shown roll reads as the sum it was', () => {
  const roll = { action: 'x', stat: 'Allure', difficulty: 'very_hard', die: 8, natural: 62, bonus: 5, shift: 20, total: 47, band: 'failure_upside' as const, label: 'Fail with an upside' }
  assert.equal(rollText(roll), 'Allure d8: 62 + 5, very hard (-20) = 47, Fail with an upside')
  assert.equal(rollText({ ...roll, die: null, bonus: 0, shift: -10, difficulty: 'easy', total: 72, label: 'Success' }), 'Allure: 62, easy (+10) = 72, Success')
  assert.equal(rollText({ ...roll, shift: 0, difficulty: 'normal', total: 67, label: 'Success at a cost' }), 'Allure d8: 62 + 5 = 67, Success at a cost')
})

test('a made character starts even and counts the points it has left', () => {
  const start = { stat_names: ['Mind', 'Allure', 'Resolve', 'Vitality', 'Essence', 'Luck'], points: 60, range: [4, 18] as [number, number] }
  const stats = startingStats(start)
  assert.deepEqual(Object.values(stats), [10, 10, 10, 10, 10, 10])
  assert.equal(pointsLeft(stats, 60), 0)
  assert.equal(pointsLeft({ ...stats, Mind: 13 }, 60), -3)
  assert.equal(pointsText(-1, 60), '1 point over of 60')
  assert.equal(pointsText(4, 60), '4 points left of 60')
  assert.equal(premadeLine({ gender: 'woman', age: 41 }), 'a woman, 41')
  assert.equal(premadeLine({ gender: 'nonbinary', age: null }), 'nonbinary')
  assert.equal(premadeLine({ gender: '', age: null }), '')
})

test('a branch says how long it ran', () => {
  assert.equal(branchLine({ turns: 1, last_at: '' }), '1 turn')
  assert.match(branchLine({ turns: 3, last_at: '2026-10-21T20:00:00' }), /^3 turns, last played /)
})

test('a journal line names its kind and what it is about', () => {
  assert.equal(journalKind({ kind: 'wound', subject: 'you', truth: 'both' }), 'Wound · you')
  assert.equal(journalKind({ kind: 'secret', subject: 'Gus', truth: 'belief' }), 'Secret · Gus (you believe)')
})

test('a quest shows the time left, or how it ended', () => {
  assert.equal(questState({ status: 'open', left: 'about 7 days left' }), 'Underway · about 7 days left')
  assert.equal(questState({ status: 'open', left: '' }), 'Underway')
  assert.equal(questState({ status: 'missed', left: '' }), 'Too late')
  assert.equal(questState({ status: 'open', left: '3 days left', kind: 'oath' }), 'Oath · Underway · 3 days left')
  assert.equal(questState({ status: 'done', left: '', kind: 'job' }), 'Job · ' + questState({ status: 'done', left: '' }))
})

test('money, gear and slots read plainly', () => {
  assert.equal(moneyText(340, { code: 'crown', symbol: 'cr.' }), '3.40 cr.')
  assert.equal(moneyText(5, { code: 'crown', name: 'silver crowns' }), '0.05 silver crowns')
  assert.equal(gearLine({ name: 'Rope, fifty feet', qty: 2 }), 'Rope, fifty feet × 2')
  assert.equal(gearLine({ name: 'Belt knife', qty: 1 }), 'Belt knife')
  assert.equal(slotsText({ used: 3.35, max: 13 }), '3.35 of 13 slots')
  assert.equal(slotsText({ used: 2.5, max: 10 }), '2.5 of 10 slots')
})

test('fightText says how the character is and who they are fighting', () => {
  assert.equal(fightText({ condition: 'unhurt', dead: false, fight: null }), '')
  assert.equal(fightText({ condition: 'hurt', dead: false, fight: null }), 'You are hurt.')
  assert.equal(fightText({ condition: 'unhurt', dead: false, fight: null, injuries: ['a limp', 'a lost eye'] }),
    'Lasting: a limp, a lost eye.')
  assert.equal(fightText({ condition: 'hurt', dead: false, fight: null, stress: 'strained, 5 of 12', injuries: ['nightmares'] }),
    'You are hurt. Nerve: strained, 5 of 12. Lasting: nightmares.')
  assert.equal(fightText({ condition: 'grazed', dead: false, fight: { round: 1, foes: [
    { name: 'the bandit', state: 'hurt', wound: null }, { name: 'the lookout', state: 'broken', wound: null }] } }),
  'You are grazed. Fighting: the bandit (hurt), the lookout (broken).')
  assert.equal(fightText({ condition: 'unhurt', dead: false, fight: { round: 1, foes: [{ name: 'the boar', state: 'hurt', wound: 2 }] } }),
    'Fighting: the boar (hurt, wound 2 of 5).')
  assert.match(fightText({ condition: 'dying', dead: true, fight: null }), /dead/)
})

test('intensityChoices offers the world\'s own preset first, by name', () => {
  const choices = intensityChoices('unflinching')
  assert.deepEqual(choices[0], ['world', "The world's own (Unflinching)"])
  assert.deepEqual(choices.map(([value]) => value), ['world', 'restrained', 'mature', 'unflinching'])
})

test('dramaChoices offers the world\'s own level first, by name', () => {
  const choices = dramaChoices('eventful')
  assert.deepEqual(choices[0], ['world', "The world's own (Eventful)"])
  assert.deepEqual(choices.map(([value]) => value), ['world', 'quiet', 'uneasy', 'eventful', 'merciless'])
})

test('haggleText says how a haggle moved today\'s prices', () => {
  assert.equal(haggleText(-15), '15% off today')
  assert.equal(haggleText(20), '20% dearer today')
  assert.equal(haggleText(0), '')
})

test('paceText says how long a turn took, its slowest step and what gave way', () => {
  assert.equal(paceText({ steps: { referee: 0.4, narrator: 9.84 }, skipped: [], budget: 30, total: 10.3 }),
    'Took 10.3 s of 30 · narrator 9.8 s')
  assert.equal(paceText({ steps: { narrator: 41 }, skipped: ['rewrite', 'contradiction'], budget: 30, total: 41.2 }),
    'Took 41.2 s of 30 · narrator 41.0 s · skipped the prose rewrite and the contradiction check for time')
})

test('the tier reads in words, with its numbers only when the dice are shown', () => {
  const tier = { tier: 'Local', words: 'known on their own street', track: 'Renown', arc: 'classic' as const, pace: 'steady' as const }
  assert.equal(tierText(tier), 'Renown: Local, known on their own street')
  assert.equal(tierText({ ...tier, points: 3, next: 12 }), 'Renown: Local, known on their own street (3 of 12)')
  assert.equal(tierText({ ...tier, tier: 'Mythic', points: 200, next: null }), 'Renown: Mythic, known on their own street (200)')
})

test('a dark track reads as a word, with its points when the dice are shown', () => {
  const track = { id: 'corruption', name: 'Corruption', word: 'tainted', changes: [] }
  assert.equal(darkText(track), 'Corruption: tainted')
  assert.equal(darkText({ ...track, points: 4, top: 10 }), 'Corruption: tainted (4 of 10)')
})

test('a loose end in the journal says what kind it is', () => {
  assert.equal(threadKind('mystery'), 'A mystery')
  assert.equal(threadKind('grudge'), 'A grudge')
})

test('journeyTo finds a destination on the travel map, ignoring a leading "the" and case', () => {
  const journeys = ['Eriane', 'the Abandoned Keep']
  assert.equal(journeyTo(journeys, 'eriane'), 'Eriane')
  assert.equal(journeyTo(journeys, 'Abandoned Keep'), 'the Abandoned Keep')
  assert.equal(journeyTo(journeys, 'The Green'), undefined)
  assert.equal(journeyTo(journeys, undefined), undefined)
})

test('sentences splits a paragraph and keeps closing quotes with their sentence', () => {
  assert.deepEqual(sentences('She waits. "You\'ll want the cellar." He nods'), ['She waits. ', '"You\'ll want the cellar." ', 'He nods'])
})

test('reworded marks only sentences whose words changed after streaming', () => {
  const draft = 'The stew has gone to skin — nobody wants it.\n\nShe wipes the bar. It is clean already.'
  const saved = 'The stew has gone to skin; nobody wants it.\n\nShe wipes the bar. The wood is already clean.'
  assert.deepEqual([...reworded(draft, saved)], ['The wood is already clean.'])
  assert.equal(reworded(saved, saved).size, 0)
})

const BANDS = [{ band: 'failure', label: 'Fail', ceiling: 30 }, { band: 'failure_upside', label: 'Fail with an upside', ceiling: 50 },
  { band: 'success_cost', label: 'Success at a cost', ceiling: 70 }, { band: 'success', label: 'Success', ceiling: 89 },
  { band: 'critical_success', label: 'Critical success', ceiling: null }] as const
const ROLL = { action: 'win her over', stat: 'Allure', difficulty: 'hard', die: 10, natural: 52, bonus: 7, shift: 10, total: 49, band: 'failure_upside', label: 'Fail with an upside' } as const

test('turnAfter builds a turn from its stream events in order', () => {
  let turn = turnAfter(NO_TURN, { stage: 'reading' })
  turn = turnAfter(turn, { actions: [{ action: 'win her over', stat: 'Allure', difficulty: 'hard' }], bands: [...BANDS] })
  turn = turnAfter(turn, { roll: { ...ROLL } })
  turn = turnAfter(turn, { stage: 'writing' })
  assert.equal(turn.stage, 'writing')
  assert.equal(turn.bands?.length, 5)
  assert.deepEqual(turn.rolls, [ROLL])
  assert.equal(turnAfter(NO_TURN, { actions: [{ action: 'a', stat: 'Luck' }] }).bands, null)
})

test('actionLine names the difficulty only while the dice are shown', () => {
  assert.equal(actionLine({ action: 'a', stat: 'Allure', difficulty: 'very_hard' }), 'Rolling Allure, very hard')
  assert.equal(actionLine({ action: 'a', stat: 'Allure' }), 'Testing your Allure')
})

test('bandSpans and markerAt lay the bands and a total on a 1 to 100 strip', () => {
  assert.deepEqual(bandSpans([...BANDS]).map(({ from, to }) => [from, to]), [[1, 30], [31, 50], [51, 70], [71, 89], [90, 100]])
  assert.equal(markerAt(124), 100)
  assert.equal(markerAt(-3), 1)
})

test('nearMiss says how close the next band was, within 5', () => {
  assert.equal(nearMiss({ ...ROLL }, [...BANDS]), '2 short of success at a cost')
  assert.equal(nearMiss({ ...ROLL, total: 40 }, [...BANDS]), '')
  assert.equal(nearMiss({ ...ROLL, total: 95, band: 'critical_success' }, [...BANDS]), '')
  assert.equal(nearMiss({ ...ROLL, total: 49, band: 'critical_failure', natural: 8 }, [...BANDS]), '')
})

test('the dice land on the roll the code made', () => {
  const roll = { action: 'Win her over', stat: 'Allure', difficulty: 'hard', die: 8, natural: 47, bonus: 5, shift: 10, total: 42, band: 'failure_upside' as const, label: 'Fail with an upside' }
  assert.deepEqual(diceFaces(roll).map((face) => face.value), ['40', '7', '5'])
  assert.deepEqual(diceFaces({ ...roll, natural: 100 }).slice(0, 2).map((face) => face.value), ['00', '0'])
  assert.deepEqual(diceFaces({ ...roll, natural: 5, die: null }).map((face) => face.value), ['00', '5'])
})

test('a tumbling die only shows faces it has', () => {
  const [tens, ones, stat] = diceFaces({ action: 'a', stat: 'Allure', difficulty: 'normal', die: 6, natural: 50, bonus: 1, shift: 0, total: 51, band: 'success_cost' as const, label: 'x' })
  assert.equal(tumbleFace(tens, 0.99), '90')
  assert.equal(tumbleFace(ones, 0), '0')
  assert.equal(tumbleFace(stat, 0), '1')
  assert.equal(tumbleFace(stat, 0.99), '6')
})

test('the 3D dice are told the faces to land on', () => {
  const roll = { action: 'a', stat: 'Allure', difficulty: 'normal', die: 8, natural: 52, bonus: 7, shift: 0, total: 59, band: 'success_cost' as const, label: 'x' }
  assert.equal(diceNotation(diceFaces(roll)), '1d100+1d10+1d8@50,2,7')
  assert.equal(diceNotation(diceFaces({ ...roll, natural: 100, die: null })), '1d100+1d10@100,10')
  assert.equal(diceNotation(diceFaces({ ...roll, natural: 7, die: null })), '1d100+1d10@100,7')
})
