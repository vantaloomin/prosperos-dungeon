import type { StoryMap as TravelMap } from '../../types'
import { EntityName } from './EntityCard'

const SIZE = 300
const PAD = 28

/** The travel map as far as your character knows it (dungeon/travel.py): where you are, where you have been, the
 *  places you have heard of and the roads between them. Setting out puts the line in the box to send. */
export function StoryMap({ map, open, onTravel }: { map: TravelMap | null; open?: boolean; onTravel: (name: string) => void }) {
  if (!map?.places.length) return null
  const xs = map.places.map((place) => place.x), ys = map.places.map((place) => place.y)
  const [left, top] = [Math.min(...xs), Math.min(...ys)]
  const span = Math.max(Math.max(...xs) - left, Math.max(...ys) - top, 0.01)
  const at = (x: number, y: number) => [PAD + (x - left) / span * (SIZE - 2 * PAD), PAD + (y - top) / span * (SIZE - 2 * PAD)]
  const where = new Map(map.places.map((place) => [place.id, at(place.x, place.y)]))
  const height = Math.max(...map.places.map((place) => where.get(place.id)![1])) + PAD
  const here = map.places.find((place) => place.here)
  return (
    <details className="story-people story-map" open={open}>
      <summary>Map{here ? ` (${here.name})` : ''}</summary>
      <svg viewBox={`0 0 ${SIZE} ${height}`} role="img" aria-label={`Map: you are at ${here?.name ?? 'an unknown place'}.`}>
        {map.roads.map((road) => {
          const [x1, y1] = where.get(road.from)!, [x2, y2] = where.get(road.to)!
          return <line key={`${road.from}-${road.to}`} x1={x1} y1={y1} x2={x2} y2={y2}
            className={`map-road danger-${road.danger}`}><title>{`${road.terrain}: ${road.hours} hours on foot`}</title></line>
        })}
        {map.places.map((place) => {
          const [x, y] = where.get(place.id)!
          return <g key={place.id} className={place.here ? 'map-place here' : place.visited ? 'map-place visited' : 'map-place'}>
            <circle cx={x} cy={y} r={place.here ? 6 : 4} />
            <text x={x} y={y - 9} textAnchor="middle">{place.name}</text>
          </g>
        })}
      </svg>
      <ul className="map-places">
        {map.places.filter((place) => !place.here).map((place) => <li key={place.id}>
          <span><EntityName entity={{ kind: 'place', id: place.id }}>{place.name}</EntityName>{place.visited ? '' : ' (heard of)'}</span>
          <button type="button" className="text-button" onClick={() => onTravel(place.name)}>Set out</button>
        </li>)}
      </ul>
    </details>
  )
}
