import assert from 'node:assert/strict'
import { test } from 'node:test'
import { cleanLook, clampScale, DEFAULT_LOOK } from '../../src/features/settings/deviceLook.ts'
import { shownScheme } from '../../src/features/settings/palette.ts'

test('text size stays between 85% and 200% in steps of 5', () => {
  assert.equal(clampScale(40), 85)
  assert.equal(clampScale(500), 200)
  assert.equal(clampScale(113), 115)
  assert.equal(clampScale(Number.NaN), 100)
})

test('a damaged saved look falls back to the defaults, keeping what is valid', () => {
  assert.deepEqual(cleanLook('nonsense'), DEFAULT_LOOK)
  assert.deepEqual(cleanLook({ textScale: 150, font: 'comic', motion: 'reduce', fontEverywhere: 'yes', layout: 'grid' }),
    { textScale: 150, font: 'default', fontEverywhere: false, motion: 'reduce', layout: 'classic', lastBeside: 'classic', stageArt: true })
  assert.equal(cleanLook({ layout: 'reader' }).layout, 'reader')
  assert.equal(cleanLook({ layout: 'custom' }).layout, 'custom')
  assert.equal(cleanLook({ lastBeside: 'custom' }).lastBeside, 'custom')
  assert.equal(cleanLook({ lastBeside: 'reader' }).lastBeside, 'classic')
  assert.equal(cleanLook({ stageArt: false }).stageArt, false)
})

test('Match my computer shows Paper or Ink, and a saved scheme shows itself', () => {
  assert.equal(shownScheme({ theme: 'system', color_scheme: 'moss' }, true), 'paper')
  assert.equal(shownScheme({ theme: 'system', color_scheme: 'moss' }, false), 'ink')
  assert.equal(shownScheme({ theme: 'paper', color_scheme: 'moss' }, false), 'paper')
  assert.equal(shownScheme({ theme: 'scheme', color_scheme: 'moss' }, true), 'moss')
  assert.equal(shownScheme(undefined, false), 'ink')
})
