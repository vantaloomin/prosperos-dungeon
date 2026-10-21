/** The quick start's "Where and when" default. */
import type { CitySummary } from '../../types'
import { categoryOf } from '../world/cityText.ts'

/** The one city the app ships. */
const SHIPPED = 'haddon-harbor'

/** The city a new companion lives in unless the user picks another: a real city of today in the user's own time zone,
 * else one on the same continent, else Haddon Harbor, the shipped city. "Anywhere, today" stays a pick. */
export function defaultCity(cities: CitySummary[], timezone: string): string {
  const today = cities.filter((city) => (city.era ?? 'modern') === 'modern' && categoryOf(city) === 'real')
  const continent = timezone.split('/')[0]
  const pick = today.find((city) => city.timezone === timezone) ?? today.find((city) => city.timezone.split('/')[0] === continent)
    ?? cities.find((city) => city.id === SHIPPED) ?? today[0]
  return pick?.id ?? ''
}
