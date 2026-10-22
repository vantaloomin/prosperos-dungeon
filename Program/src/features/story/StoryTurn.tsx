import { Check, Dices, PenLine } from 'lucide-react'
import type { BandStep, HiddenRoll, StoryRoll, TurnSoFar } from '../../types'
import { actionLine, bandSpans, isShown, markerAt, nearMiss, rollText } from './storyText'

const SUCCESS = new Set(['success_cost', 'success', 'critical_success'])

/** One roll: with the dice shown, the action, stat and difficulty, where the total landed on the ruleset's band
 *  strip and the band in words; with them hidden, only that a stat was tested. `live` lets the marker land. */
export function RollCard({ roll, bands, live }: { roll: StoryRoll | HiddenRoll; bands?: BandStep[] | null; live?: boolean }) {
  if (!isShown(roll)) return (
    <p className="roll-hidden" title={roll.action}><Dices aria-hidden="true" />Your {roll.stat} is tested</p>
  )
  const close = bands ? nearMiss(roll, bands) : ''
  return (
    <div className="roll-card" title={rollText(roll)} aria-label={`${roll.action}: ${roll.stat}, ${roll.difficulty.replace('_', ' ')}. ${roll.label}, ${roll.total}.`}>
      <div className="roll-what">
        <span className="subtle">{roll.action}</span>
        <strong>{roll.stat} · {roll.difficulty.replace('_', ' ')}</strong>
      </div>
      {!!bands?.length && <div className="roll-strip" aria-hidden="true">
        {bandSpans(bands).map((step) => <span key={step.band} className={`band-${step.band}`} style={{ flexGrow: step.to - step.from + 1 }}
          title={`${step.label}: ${step.from}${step.ceiling === null ? '+' : `–${step.to}`}`} />)}
        <i className={live ? 'roll-marker landing' : 'roll-marker'} style={{ left: `${markerAt(roll.total)}%` }} />
      </div>}
      <div className="roll-result">
        <span className={SUCCESS.has(roll.band) ? 'roll-band won' : 'roll-band'}>{roll.label}</span>
        <span className="subtle">{close || roll.total}</span>
      </div>
    </div>
  )
}

/** A turn under way before its narration: what the game is doing (reading the line, rolling, writing) and each roll
 *  as it lands, so the wait shows its work (dungeon/story.py answer). The rolls stay once the prose streams. */
export function TurnLive({ turn, writing }: { turn: TurnSoFar; writing: boolean }) {
  const rolled = turn.rolls.length >= turn.actions.length
  return (<>
    {turn.rolls.map((roll, index) => <RollCard key={index} roll={roll} bands={turn.bands} live />)}
    {!writing && <ol className="turn-steps" aria-label="What the game is doing">
      <li className={turn.actions.length || turn.stage === 'writing' ? 'done' : 'now'}>
        {turn.actions.length || turn.stage === 'writing' ? <Check aria-hidden="true" /> : <span className="turn-dot" />}
        {turn.actions.length ? `Read your move: ${turn.actions.map((action) => action.action).join(', then ')}` : 'Reading your move'}
      </li>
      {turn.actions.map((action, index) => <li key={index} className={index < turn.rolls.length ? 'done' : 'now'}>
        {index < turn.rolls.length ? <Check aria-hidden="true" /> : <Dices aria-hidden="true" />}{actionLine(action)}
      </li>)}
      <li className={turn.stage === 'writing' && rolled ? 'now' : 'later'}><PenLine aria-hidden="true" />The narrator writes what happens</li>
    </ol>}
  </>)
}
