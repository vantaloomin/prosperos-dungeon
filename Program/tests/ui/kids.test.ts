import assert from 'node:assert/strict'
import { test } from 'node:test'
import { kidLine, kidsHint, whereHint, wherePick } from '../../src/features/character/familyText.ts'
import type { Kid, KidsView } from '../../src/types.ts'

const kid = (changes: Partial<Kid>): Kid => ({
  id: 'k1', name: 'Leo', pronouns: 'he/him', born_on: '2019-05-01', age: 7, age_text: '7', relation: 'son', ...changes,
})
const view = (changes: Partial<KidsView>): KidsView => ({
  shown: true, how: 'description', kids: [kid({})], other: { name: 'Mark', role: 'ex-husband' }, pattern: 'with_them',
  pattern_how: 'fixed', patterns: [], ...changes,
})

test('one of their kids reads as name, age and son or daughter', () => {
  assert.equal(kidLine(kid({})), 'Leo, 7, son')
  assert.equal(kidLine(kid({ name: 'Ivy', age_text: 'a newborn', relation: 'daughter' })), 'Ivy, newborn, daughter')
  assert.equal(kidLine(kid({ age_text: '7 months old' })), 'Leo, 7 months old, son')
})

test('the hints say where the kids came from and who decided where they live', () => {
  assert.equal(kidsHint(view({}), 'Dana Reyes'), "Read from Dana's description. Take a child out of their life if they shouldn't be there.")
  assert.match(kidsHint(view({ how: 'town' }), 'Dana'), /while living in town/)
  assert.match(kidsHint(view({ how: 'seeded' }), 'Dana'), /^Picked by the app for Dana\./)
  assert.equal(whereHint(view({}), 'Dana'), "Read from Dana's description. Mark, their other parent, is Dana's ex-husband.")
  assert.equal(whereHint(view({ pattern_how: 'seeded', detail: "with Dana, every other weekend at Mark's", other: { name: 'Mark Lowe', role: 'ex-husband' } }), 'Dana'),
    "Picked by the app: with Dana, every other weekend at Mark's. Mark, their other parent, is Dana's ex-husband.")
  assert.equal(whereHint(view({ pattern_how: 'set', other: null }), 'Dana'), 'You set this.')
})

test('the first choice of where the kids live names the description or the app', () => {
  assert.equal(wherePick(view({}), 'Sam', 'Mostly with Sam'), "From Sam's description (Mostly with Sam)")
  assert.equal(wherePick(view({ pattern_how: 'seeded' }), 'Dana', 'Mostly with Dana'), 'Let the app decide (Mostly with Dana)')
  assert.equal(wherePick(view({ pattern_how: 'set' }), 'Dana', 'Half and half'), 'Let the app decide (what fits them)')
})
