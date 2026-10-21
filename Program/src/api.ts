// Request helper adapted from prosperos-study src/api.ts at bbcbde4: the Dungeon's client header and error codes.
export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message) }
}

function errorMessage(status: number, data: { detail?: unknown }): string {
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) return data.detail.map((item) => item.msg).join('; ')
  return `The Dungeon could not finish that (error ${status}). Please try again.`
}

let world: string | null = null

/** The world this page shows (src/features/worlds/useWorlds.ts). Sent with every request, so a page left open in
 * one world never changes another the PC or phone has since moved to (dungeon/main.py stay_in_world). */
export function openedIn(id: string) { world = id }

function headers(type: string): Record<string, string> {
  return { 'Content-Type': type, 'X-Dungeon-Client': 'workspace', ...(world ? { 'X-Dungeon-World': world } : {}) }
}

export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: headers('application/json'),
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the Dungeon. Check that it is still running.', 0, 'offline')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw failure(response.status, data)
  return data as T
}

/** A workspace switched in another tab reloads this one on the story. */
function failure(status: number, data: { detail?: unknown; code?: string }): ApiError {
  if (data.code === 'world_changed') { window.location.hash = '#story'; window.location.reload() }
  return new ApiError(errorMessage(status, data), status, data.code)
}

export { newId } from './ids.ts'

