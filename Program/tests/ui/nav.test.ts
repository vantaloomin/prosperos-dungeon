import assert from 'node:assert/strict'
import { test } from 'node:test'
import { chatsTarget, inChats, railCurrent } from '../../src/features/nav/navText.ts'

test('Chats holds the list, every chat, the profile tabs, groups and worlds', () => {
  for (const view of ['chats', 'conversation', 'memories', 'character', 'portraits', 'groups', 'group/abc', 'worlds']) assert.equal(inChats(view), true, view)
  for (const view of ['today', 'map', 'story', 'settings/models']) assert.equal(inChats(view), false, view)
})

test('the Chats tab returns to where the user was, and to the list when tapped inside a chat', () => {
  assert.equal(chatsTarget('today', 'group/abc'), 'group/abc')
  assert.equal(chatsTarget('settings', 'chats'), 'chats')
  assert.equal(chatsTarget('conversation', 'conversation'), 'chats')
  assert.equal(chatsTarget('memories', 'memories'), 'chats')
})

test('the side rail lights Memories on its own and Profile on the other profile tabs', () => {
  assert.equal(railCurrent('memories', 'memories'), true)
  assert.equal(railCurrent('conversation', 'memories'), false)
  assert.equal(railCurrent('conversation', 'character'), true)
  assert.equal(railCurrent('today', 'map/abc'), true)
  assert.equal(railCurrent('groups', 'group/abc'), true)
  assert.equal(railCurrent('settings', 'settings/debug'), true)
})
