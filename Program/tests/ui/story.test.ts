import assert from 'node:assert/strict'
import { test } from 'node:test'
import { aroundText, branchLine, journalKind, personLine, placeGroups, pointsLeft, pointsText, premadeLine, rollText, sceneTime, startingStats } from '../../src/features/story/storyText.ts'

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
    doing: 'working as the barista', place: { id: 'p', name: 'The Daily Grind', city_id: 'baltimore' } }
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
