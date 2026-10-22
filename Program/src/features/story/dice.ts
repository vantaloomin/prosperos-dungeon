import { useEffect, useState } from 'react'
import type { StoryRoll } from '../../types'
import { diceFaces, tumbleFace, type DieFace } from './storyText'

// The dice only act out a roll the code already made (dungeon/rules/marvel.py): each one tumbles, then lands on its
// real face, one after another; the strip and the band show once the last has landed.
const TICK_MS = 70
const landsAt = (index: number) => 650 + index * 280

/** The user's reduced-motion choice in Settings, else the computer's. */
function calm(): boolean {
  const motion = document.documentElement.dataset.motion
  return motion === 'reduce' || (motion !== 'full' && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
}

export interface Tumble { faces: DieFace[]; shown: string[]; landed: boolean[]; done: boolean; skip: () => void }

/** The dice of one roll as they tumble: `rolling` false (a saved roll, or reduced motion) shows them landed. */
export function useTumble(roll: StoryRoll, rolling: boolean): Tumble {
  const faces = diceFaces(roll)
  const end = landsAt(faces.length - 1)
  const [elapsed, setElapsed] = useState(() => (rolling && !calm() ? 0 : end))
  const [picks, setPicks] = useState<number[]>(() => faces.map(() => 0))
  const done = elapsed >= end
  useEffect(() => {
    if (done) return
    const started = Date.now() - elapsed
    const timer = window.setInterval(() => {
      setElapsed(Date.now() - started)
      setPicks(faces.map(() => Math.random()))
    }, TICK_MS)
    return () => window.clearInterval(timer)
    // The timer runs once per roll; it reads elapsed only to resume where it stood.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done])
  const landed = faces.map((_, index) => elapsed >= landsAt(index))
  return {
    faces, landed, done,
    shown: faces.map((face, index) => (landed[index] ? face.value : tumbleFace(face, picks[index] ?? 0))),
    skip: () => setElapsed(end),
  }
}
