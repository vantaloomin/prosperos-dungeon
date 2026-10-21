"""Request bodies. Input mirrors prosperos-study server/models.py at bbcbde4."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Relationship = Literal['friendship', 'romance', 'mentor', 'family', 'other']
Layer = Literal['user_fact', 'shared_experience', 'plan', 'temporary', 'relationship', 'companion_life']
PlanStatus = Literal['proposed', 'agreed', 'postponed', 'cancelled', 'completed']
EventKind = Literal['routine', 'plan', 'ordinary', 'thread']
BlockKind = Literal['work', 'study', 'errand', 'leisure', 'social', 'rest', 'sleep']
ClockTime = Annotated[str, Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')]
Intensity = Literal['mild', 'moderate', 'strong']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Looks(Input):
    """What they look like, field by field (dungeon/world/looks.py); an empty field is drawn for them."""
    age: int | None = Field(default=None, ge=18, le=120)
    height_cm: int | None = Field(default=None, ge=120, le=230)
    weight_kg: int | None = Field(default=None, ge=35, le=250)
    build: str = Field(default='', max_length=120)
    skin: str = Field(default='', max_length=120)
    face: str = Field(default='', max_length=120)
    jaw: str = Field(default='', max_length=120)
    nose: str = Field(default='', max_length=120)
    eyes: str = Field(default='', max_length=120)
    eye_shape: str = Field(default='', max_length=120)
    hair: str = Field(default='', max_length=200)
    facial_hair: str = Field(default='', max_length=120)
    feature: str = Field(default='', max_length=200)
    # The values the app filled in when a townsperson became a companion (dungeon/cast.py): a field still equal to
    # its drawn value is the app's, so it may change over time (dungeon/life/grooming.py); one the user edited is not.
    drawn: dict[str, int | str] = Field(default_factory=dict, max_length=20)


PersonalityTrait = Literal['social', 'warmth', 'order', 'curiosity', 'stress']


DraftField = Literal['identity', 'personality', 'voice', 'skills', 'flaws', 'interests', 'background', 'appearance',
                     'routine', 'life_themes', 'schedule']


class LoreFile(Input):
    """A lorebook file (JSON or .lorebook), base64 encoded (dungeon/lore.py)."""
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)


class LoreSwitch(Input):
    """Turn an imported lorebook, or one of its entries, on or off (dungeon/lore.py)."""
    enabled: bool


class PromptUpdate(Input):
    text: str = Field(min_length=1, max_length=20000)


HEX = r'^#[0-9a-fA-F]{6}$'


class Palette(Input):
    """A custom color scheme, as Prospero's Study's custom palette."""
    accent: str = Field(pattern=HEX)
    background: str = Field(pattern=HEX)
    surface: str = Field(pattern=HEX)
    text: str = Field(pattern=HEX)


class SettingsUpdate(Input):
    user_timezone: str | None = Field(default=None, max_length=64)
    # 'detected': the interface reporting this PC's zone; 'pc': Use this PC's timezone; otherwise chosen.
    user_timezone_source: Literal['detected', 'pc', 'chosen'] | None = None
    color_scheme: Literal['ink', 'slate', 'umber', 'moss', 'wine', 'ash', 'custom'] | None = None
    custom_palette: Palette | None = None
    # 'system' matches the computer (Paper or Ink), 'paper' is the light profile, 'scheme' uses color_scheme.
    theme: Literal['system', 'scheme', 'paper'] | None = None
    show_odds: bool | None = None
    # The adult side of life (dungeon/world/intimacy.py) and whether townsfolk's shows.
    adult_side: bool | None = None
    show_adult_side: bool | None = None
    # Automatic backups of every world (dungeon/auto_backup.py).
    auto_backups: Literal['off', 'daily', 'weekly'] | None = None
    # The first-run notice: the story is AI written, and the user is 18 or older. Only ever confirmed.
    ai_notice_confirmed: Literal[True] | None = None


class ConnectionUpdate(Input):
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=4000)
    max_output_tokens: int = Field(default=800, ge=64, le=128000)
    context_tokens: int = Field(default=16000, ge=1024, le=2000000)
    timeout_seconds: int = Field(default=180, ge=10, le=1800)
    # Optional embedding model on the same connection; empty keeps recall keyword-only.
    embedding_model: str | None = Field(default=None, max_length=200)


Gender = Literal['woman', 'man', 'nonbinary', '']
Birthday = Annotated[str, Field(pattern=r'^(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))?$')]


# Lifespans (dungeon/world/lifespans.py `SPANS`): what How long they live offers, besides as their kind.
LIFESPANS = (80, 150, 300, 600, 1000)
# A persona's age: up to 120, and up to 5,000 for a long-lived kind (dungeon/worlds.py).
PERSONA_AGES = (120, 5000)


class PersonaPet(Input):
    """One of the user's own pets (dungeon/life/pets.py gives it a life): their words, never invented."""
    name: str = Field(min_length=1, max_length=40, pattern=r'\S')
    kind: str = Field(default='cat', min_length=1, max_length=20)
    looks: str = Field(default='', max_length=160)
    # Years old, when the user says; otherwise the pet keeps the birth date it was given.
    age: int | None = Field(default=None, ge=0, le=90)


class PersonaInput(Input):
    """Who the user is in a persona's worlds (dungeon/worlds.py). Only the user says this; blanks stay blank."""
    name: str | None = Field(None, max_length=80)
    gender: Gender | None = None
    # Past 120 only for a long-lived kind, picked below or read from About you (dungeon/worlds.py checks it).
    age: int | None = Field(None, ge=18, le=PERSONA_AGES[1])
    about: str | None = Field(None, max_length=2000)
    birthday: Birthday | None = None
    pets: list[PersonaPet] | None = Field(None, max_length=8)
    # Kind and How long they live (dungeon/world/lifespans.py), as on the Character page: '' and None leave both to
    # their words, 0 years is "Doesn't age".
    kind: str | None = Field(None, max_length=40, pattern=r'^[a-z0-9-]*$')
    lifespan: int | None = None

    @field_validator('lifespan')
    @classmethod
    def listed(cls, value):
        if value not in (None, 0, *LIFESPANS):
            raise ValueError('Pick one of the lifespans listed.')
        return value


class NewPersona(PersonaInput):
    """A new persona, and the city their world is in: the current one unless the user picks another, or
    `somewhere-new` for the app to pick (dungeon/worlds.py)."""
    city_id: str | None = Field(None, min_length=1, max_length=120)


class HomeChange(Input):
    """Where the user lives in a world (dungeon/life/where.py): a city and a neighbourhood there; a blank
    neighbourhood lets the app pick one."""
    city_id: str = Field(min_length=1, max_length=120)
    neighbourhood: str = Field(default='', max_length=120)


class WorldChange(Input):
    """Rename a world, or give it to another persona."""
    name: str | None = Field(None, max_length=80)
    persona_id: str | None = Field(None, min_length=1, max_length=100)


class NewWorld(Input):
    """A new world: for the active persona and in the current city unless these say otherwise."""
    persona_id: str | None = Field(None, min_length=1, max_length=100)
    name: str | None = Field(None, max_length=80)
    city_id: str | None = Field(None, min_length=1, max_length=120)


