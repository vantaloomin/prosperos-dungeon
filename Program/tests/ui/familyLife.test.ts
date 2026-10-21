import assert from 'node:assert/strict'
import { test } from 'node:test'
import { FAMILY_LIFE_LEVELS } from '../../src/features/character/familiesText.ts'

test('the Family life slider has four steps, easy kids first', () => {
  assert.deepEqual(FAMILY_LIFE_LEVELS.map((item) => item.label), ['Easy', 'Gentle', 'True to life', 'Chaotic'])
})
