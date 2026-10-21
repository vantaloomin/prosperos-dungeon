import assert from 'node:assert/strict'
import { test } from 'node:test'
import { SETTINGS_TABS, availableTabs, pickTab, searchSettings } from '../../src/features/settings/sections.ts'
import { readAdvanced, writeAdvanced } from '../../src/features/settings/advanced.ts'
import { groupPrompts, placeholderHint } from '../../src/features/settings/prompts.ts'

test('a deep link opens its tab, and an unknown or unavailable one opens the first', () => {
  assert.equal(pickTab('images'), 'images')
  assert.equal(pickTab(undefined), 'general')
  assert.equal(pickTab('nonsense'), 'general')
  assert.deepEqual(availableTabs().map((tab) => tab.id), ['general', 'models', 'world', 'images', 'data', 'debug'])
})

test('search finds sections by title, tab name or keyword, needing every word', () => {
  const found = (query: string) => searchSettings(query).map((match) => match.section.heading)
  assert.deepEqual(found('timezone'), ['time-heading'])
  assert.deepEqual(found('TIMEZONE'), ['time-heading'])
  assert.deepEqual(found('restore'), ['backup-heading'])
  assert.deepEqual(found('logging'), ['model-calls-heading'])
  assert.deepEqual(found('anthropic key'), ['models-heading'])
  assert.deepEqual(found('weather'), [])
  assert.deepEqual(found('   '), [])
})

test('every section heading is listed once', () => {
  const headings = SETTINGS_TABS.flatMap((tab) => tab.sections.map((section) => section.heading))
  assert.equal(new Set(headings).size, headings.length)
})

test('the Advanced tab shows only with the switch on, and search still finds it', () => {
  assert.ok(!availableTabs().some((tab) => tab.id === 'advanced'))
  assert.equal(availableTabs(true).at(-1)?.id, 'advanced')
  assert.equal(pickTab('advanced'), 'general')
  assert.equal(pickTab('advanced', true), 'advanced')
  const found = searchSettings('prompt')
  assert.deepEqual(found.map((match) => match.section.heading), ['prompts-heading'])
  assert.ok(found[0].tab.advanced)
})

test('the advanced switch is remembered by the browser and off by default', () => {
  const values = new Map<string, string>()
  const store = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value) }, removeItem: (key: string) => { values.delete(key) } }
  assert.equal(readAdvanced(store), false)
  writeAdvanced(store, true)
  assert.equal(readAdvanced(store), true)
  writeAdvanced(store, false)
  assert.equal(readAdvanced(store), false)
  assert.equal(readAdvanced(undefined), false)
  const broken = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') }, removeItem: () => { throw new Error('blocked') } }
  assert.equal(readAdvanced(broken), false)
  writeAdvanced(broken, true)
})

test('prompts are grouped in order and their placeholders explained', () => {
  const prompt = (name: string, group: string, placeholders: string[] = [], help: Record<string, string> = {}) =>
    ({ name, group, label: name, description: '', text: '', default: '', customized: false, outdated: false, placeholders, placeholder_help: help })
  const groups = groupPrompts([prompt('a', 'Chat and life'), prompt('b', 'Character drafting'), prompt('c', 'Chat and life')])
  assert.deepEqual(groups.map(([group, items]) => [group, items.map((item) => item.name)]), [['Chat and life', ['a', 'c']], ['Character drafting', ['b']]])
  assert.equal(placeholderHint(prompt('x', 'g', ['name', 'reason'], { name: "the companion's name" })), "Must keep: {{name}} (the companion's name), {{reason}}.")
  assert.equal(placeholderHint(prompt('x', 'g')), '')
})
