import { test } from 'node:test'
import assert from 'node:assert/strict'
import { companionsLine, initial, personaName, personaRef, personaTitle, whereLine } from '../../src/features/worlds/worldsText.ts'

test('a persona without a name is never called You', () => {
  assert.equal(personaName({ name: '  ' }), '')
  assert.equal(personaTitle({ name: '' }), 'Your first persona')
  assert.equal(personaRef({ name: '' }), 'this persona')
  assert.equal(personaRef({ name: 'Sam' }), 'Sam')
  assert.equal(initial({ name: 'sam' }), 'S')
  assert.equal(initial({ name: '' }), '')
  assert.equal(whereLine({ name: 'Sam' }, { name: 'Baltimore' }), 'Sam · Baltimore')
  assert.equal(whereLine({ name: '' }, { name: 'Baltimore' }), 'Baltimore')
})

test('a world lists its companions briefly', () => {
  assert.equal(companionsLine({ companions: [] }), 'No companions yet')
  assert.equal(companionsLine({ companions: ['Mira', 'Sally'] }), 'Mira and Sally')
  assert.equal(companionsLine({ companions: ['A', 'B', 'C', 'D', 'E'] }), 'A, B and 3 more')
})
