import assert from 'node:assert/strict'
import test from 'node:test'
import { mapPlace } from '../../src/features/today/todayText.ts'

test('a place that is no place in town has no map link in the day list', () => {
  assert.equal(mapPlace({ id: '~home' }), null)
  assert.equal(mapPlace({ id: 'berthas' }), 'berthas')
  assert.equal(mapPlace(undefined), null)
})
