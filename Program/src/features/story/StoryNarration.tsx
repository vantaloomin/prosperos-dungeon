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

const shortened = (text: string) => text.length > 120 ? `${text.slice(0, 117).trimEnd()}…` : text

/** A narration: its flagged paragraphs marked with why and a Rewrite button, and any selected passage rewritable. */
export function StoryNarration({ message, onRewrite, onSwitch }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [chosen, setChosen] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  useEffect(() => { if (chosen) form.current?.scrollIntoView?.({ block: 'nearest' }) }, [chosen])
  const flags = new Map((message.flags ?? []).map((flag) => [flag.passage, flag.why]))
  const pick = () => {
    const selection = window.getSelection()
    const text = selection?.toString().trim() ?? ''
    if (onRewrite && text && selection?.anchorNode && box.current?.contains(selection.anchorNode)) setChosen(text)
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
