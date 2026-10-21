/** Settings is split into tabs; this lists them, what each holds, and the words a search finds them by. */

export type SettingsTab = 'general' | 'models' | 'world' | 'images' | 'data' | 'debug' | 'advanced'

export interface SettingsSection {
  /** The id of the section's heading, used to land on it from a search result. */
  heading: string
  title: string
  keywords: string
}

export interface SettingsTabInfo {
  id: SettingsTab
  label: string
  /** Listed only while "Show advanced settings" is on. */
  advanced?: boolean
  sections: SettingsSection[]
}

export const SETTINGS_TABS: SettingsTabInfo[] = [
  {
    id: 'general', label: 'General', sections: [
      { heading: 'time-heading', title: 'Your time', keywords: 'timezone time zone clock date pc' },
      { heading: 'appearance-heading', title: 'Appearance', keywords: 'appearance look colors colours theme dark light paper ink palette text size font motion' },
    ],
  },
  {
    id: 'models', label: 'Models', sections: [
      { heading: 'hardware-heading', title: 'This computer', keywords: 'hardware graphics card gpu vram memory ram nvidia fit warning slow local' },
      { heading: 'models-heading', title: 'Models', keywords: 'model connection provider api key openai anthropic openrouter google local kobold codex claude profile story narrator recall temperature' },
      { heading: 'recall-profiles-heading', title: 'Recall', keywords: 'recall embedding embeddings semantic memory search ollama lm studio openai nomic qwen gemma profile' },
      { heading: 'local-programs-heading', title: 'Local programs', keywords: 'launch start open run lm studio ollama kobold koboldcpp comfyui local program auto start boot' },
      { heading: 'recall-heading', title: 'Built-in recall', keywords: 'recall embedding embeddings semantic llama.cpp llama-server gguf gemma embeddinggemma qwen local memory search' },
    ],
  },
  {
    id: 'world', label: 'World', sections: [
      { heading: 'cities-heading', title: 'Cities', keywords: 'city cities places home world pack' },
      { heading: 'adult-side-heading', title: 'Adult side of life', keywords: 'adult adults nsfw 18 sex sexual sexuality orientation gay straight bisexual kink adventurous drive intimacy' },
      { heading: 'hidden-values-heading', title: 'Hidden values', keywords: 'hidden values show reveal odds dice why it went adult side' },
    ],
  },
  {
    id: 'images', label: 'Images', sections: [
      { heading: 'images-heading', title: 'Images', keywords: 'image pictures photos comfyui krea codex nsfw backend' },
    ],
  },
  {
    id: 'data', label: 'Backups', sections: [
      { heading: 'backup-heading', title: 'Backups', keywords: 'backup restore data export archive folder' },
    ],
  },
  {
    id: 'debug', label: 'Debug', sections: [
      { heading: 'debug-heading', title: 'Debug time', keywords: 'debug test testing time travel jump skip ahead days fast forward speed accelerate spoof date clock' },
      { heading: 'model-calls-heading', title: 'Record model calls', keywords: 'log logs logging record recording requests responses raw sent strange reply support troubleshoot' },
      { heading: 'townsfolk-mix-heading', title: 'Townsfolk mix', keywords: 'townsfolk mix ratio ratios shares population generation generate new world reseed gender women men nonbinary height build weight beard facial hair orientation sexuality gay lesbian bisexual straight adult side adventurous drive sliders' },
    ],
  },
  {
    id: 'advanced', label: 'Advanced', advanced: true, sections: [
      { heading: 'prompts-heading', title: 'Prompts', keywords: 'advanced prompt prompts system instructions wording narrator story craft writing rules authors note power user' },
    ],
  },
]

export function availableTabs(advanced = false): SettingsTabInfo[] {
  return SETTINGS_TABS.filter((tab) => advanced || !tab.advanced)
}

/** The tab to show for a deep link: the one asked for when it is available, else the first one. */
export function pickTab(requested: string | undefined, advanced = false): SettingsTab {
  const tabs = availableTabs(advanced)
  return (tabs.find((tab) => tab.id === requested) ?? tabs[0]).id
}

export interface SettingsMatch { tab: SettingsTabInfo; section: SettingsSection }

/**
 * Sections whose title, tab or keywords contain every word of the query. Advanced sections are found
 * even while hidden; picking one turns "Show advanced settings" on.
 */
export function searchSettings(query: string): SettingsMatch[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return []
  return availableTabs(true).flatMap((tab) => tab.sections
    .filter((section) => {
      const text = `${section.title} ${tab.label} ${section.keywords}`.toLowerCase()
      return words.every((word) => text.includes(word))
    })
    .map((section) => ({ tab, section })))
}
