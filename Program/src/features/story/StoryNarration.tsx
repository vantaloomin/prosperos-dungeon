import { useEffect, useRef, useState } from 'react'
import { PenLine, Repeat } from 'lucide-react'
import type { StoryMessage } from '../../types'
import { InfoTip } from '../../components/InfoTip'

interface Props {
  message: StoryMessage
  /** Rewrite a passage in new words, with an optional note; the dice and the record's facts stay (dungeon/passages.py). */
  onRewrite?: (id: string, passage: string, note: string) => Promise<void>
  /** Switch between the wording before the last rewrite and the rewrite. */
  onSwitch?: (id: string) => Promise<void>
}

/** Where the Rewrite chip sits in the narration box: just under the end of the selected range. */
function chipAt(range: Range, box: HTMLElement): { top: number; left: number } {
  const end = range.getBoundingClientRect?.()
  if (!end) return { top: 0, left: 0 }
  const frame = box.getBoundingClientRect()
  return { top: end.bottom - frame.top + 4, left: Math.max(0, end.right - frame.left - 80) }
}

const shortened = (text: string) => text.length > 120 ? `${text.slice(0, 117).trimEnd()}…` : text

/** A narration: its flagged paragraphs marked with why and a Rewrite button. Selecting a passage shows a small
 *  Rewrite chip beside it, and only the chip opens the form, so selecting text to copy it costs nothing. */
export function StoryNarration({ message, onRewrite, onSwitch }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [chosen, setChosen] = useState('')
  // A selected passage, and where its chip sits inside the narration box.
  const [offer, setOffer] = useState<{ text: string; top: number; left: number } | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  useEffect(() => { if (chosen) form.current?.scrollIntoView?.({ block: 'nearest' }) }, [chosen])
  useEffect(() => {
    if (!offer) return
    // The chip goes when the selection does (a click elsewhere, a new selection outside this narration).
    const gone = () => { if (!window.getSelection()?.toString().trim()) setOffer(null) }
    document.addEventListener('selectionchange', gone)
    return () => document.removeEventListener('selectionchange', gone)
  }, [offer])
  const flags = new Map((message.flags ?? []).map((flag) => [flag.passage, flag.why]))
  const pick = () => {
    const selection = window.getSelection()
    const text = selection?.toString().trim() ?? ''
    if (!onRewrite || !text || !selection?.anchorNode || !box.current?.contains(selection.anchorNode) || !selection.rangeCount) return
    setOffer({ text, ...chipAt(selection.getRangeAt(0), box.current) })
  }
  const act = async (work: () => Promise<void>) => {
    setBusy(true)
    try { await work(); setChosen(''); setNote('') } finally { setBusy(false) }
  }
  return (<>
    <div className="story-narration" ref={box} onMouseUp={pick} onKeyUp={pick} onTouchEnd={pick}>
      {message.text.split(/\n{2,}/).map((part, index) => {
        const why = flags.get(part.trim())
        if (!why) return <p key={index}>{part}</p>
        return (
          <div key={index} className="story-flagged">
            <p>{part}</p>
            {onRewrite && <span className="story-flag">
              <InfoTip id={`flag-${message.id}-${index}`} label="why this passage is marked" text={why.join(' ')} />
              <button type="button" className="text-button" onClick={() => setChosen(part.trim())}><PenLine aria-hidden="true" />Rewrite</button>
            </span>}
          </div>)
      })}
      {offer && onRewrite && <button type="button" className="button story-rewrite-chip" style={{ top: offer.top, left: offer.left }}
        onMouseDown={(event) => event.preventDefault()} onClick={() => { setChosen(offer.text); setOffer(null) }}>
        <PenLine aria-hidden="true" />Rewrite</button>}
    </div>
    {chosen && onRewrite && <form ref={form} className="story-rewrite" onSubmit={(event) => { event.preventDefault(); void act(() => onRewrite(message.id, chosen, note)) }}>
      <p className="subtle">Rewrite &ldquo;{shortened(chosen)}&rdquo; in new words. The dice and what happened stay the same.</p>
      <label>What to change (optional)
        <input value={note} maxLength={300} placeholder="Less purple, she wouldn't say that…" onChange={(event) => setNote(event.target.value)} />
      </label>
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={busy}><PenLine aria-hidden="true" />{busy ? 'Rewriting…' : 'Rewrite'}</button>
        <button type="button" className="text-button" disabled={busy} onClick={() => setChosen('')}>Cancel</button>
      </div>
    </form>}
    {message.previous && onSwitch && <button type="button" className="text-button story-back" disabled={busy} onClick={() => void act(() => onSwitch(message.id))}
      title="Switch between the wording before your last rewrite and the rewrite."><Repeat aria-hidden="true" />Switch wording</button>}
  </>)
}
