import { Bandage, BookOpen, Coins, HeartCrack, Package, ScrollText } from 'lucide-react'
import type { ReceiptChip } from '../../types'

const ICONS = { coins: Coins, item: Package, hurt: HeartCrack, injury: Bandage, quest: ScrollText, learned: BookOpen }

/** The turn receipt (dungeon/receipt.py): what the turn changed, in chips under its narration. */
export function TurnReceipt({ chips }: { chips?: ReceiptChip[] }) {
  if (!chips?.length) return null
  return (
    <ul className="turn-receipt" aria-label="What changed this turn">
      {chips.map((chip, index) => {
        const Icon = ICONS[chip.kind]
        return <li key={index} className={`receipt-chip ${chip.tone}`}><Icon aria-hidden="true" />{chip.text}</li>
      })}
    </ul>
  )
}
