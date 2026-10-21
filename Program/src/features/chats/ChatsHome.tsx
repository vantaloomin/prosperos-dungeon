import type { View } from '../../companion'
import { PersonaButton } from '../worlds/WorldButton'
import { ChatList } from './ChatsPanel'

/**
 * The phone's Chats tab: every chat in one list, the way a messaging app opens. Your persona's avatar sits top left
 * and opens Worlds.
 */
export function ChatsHome({ go }: { go: (view: View) => void }) {
  return (
    <section className="chats-home" aria-labelledby="chats-heading">
      <header className="chats-home-header">
        <PersonaButton onOpen={() => go('worlds')} />
        <h1 id="chats-heading">Chats</h1>
      </header>
      <ChatList go={go} />
    </section>
  )
}
