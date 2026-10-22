"""The playtest scenarios: Milestone 1 and 2's "done when" lists (docs/roadmap.md), played as a player would.

Each is a function of a `Play` (playtest.py). Lines are what a player types; `expect` adds checks.
"""


def town(play):
    """M1: a premade in Kingswood, talking to people, the Heartwood contract, and what the character knows."""
    play.start('agna-holt')
    play.say('I take a seat near the fire and look around the room, taking in who is drinking here tonight.',
             {'no_roll': True})
    play.say('"Evening," I say to whoever is behind the bar. "Ale, and whatever you hear about this contract on '
             'the green."')
    play.say('I ask the barkeep who in town would know the most about the Heartwood, and why the guild pays double.')
    play.people()
    play.move('the-green')
    play.say('I read the notice posted on the green, all of it, and check who has signed so far.')
    play.move('guild-factor')
    play.say('I tell the factor I want to sign on for the Heartwood crews, and ask what the grey-fletched arrows '
             'mean.')
    play.say('I lean on him: "Somebody is threatening your crews. Tell me what you know or find another sword."',
             {'roll': True})
    play.journal()
    play.say('OOC: what quests does my character know about right now?', {'no_roll': True})


def shop(play):
    """M1: inventory and the one shop: the counter, buying in the window and in the story, haggling, selling."""
    play.start('tobin-pell')
    play.move('pell-provisions')
    play.gear()
    play.say('I look over the shelves and ask what a coil of rope and a lantern would cost me.', {'no_roll': True})
    play.say('I haggle hard over the lantern, reminding the keeper I am family and that the Guild pays late.',
             {'roll': True})
    play.gear()
    play.say('I buy the lantern and two loaves of bread.')
    play.gear()
    play.buy('rope')
    play.say('I try to haggle again on the rope, since it went so well last time.')
    play.say('I sell my ledger book back over the counter.')
    play.gear()
    play.say('I pocket a candle from the shelf while the keeper is turned away.', {'roll': True})
    play.gear()
    play.journal()


def heartwood(play):
    """M1: into the dangerous place, a fight, getting hurt, and going back to try again with new dice."""
    play.start('agna-holt')
    play.move('border-stones')
    play.say('I wait by the border stones a while and watch the far bank for any sign of the wardens.')
    play.move('the-heartwood')
    for line in ('I push on into the Heartwood along the old trail, sword unwrapped and ready.',
                 'I go deeper, looking for the oldest trees, the ones the guild means to fell.',
                 'I keep going, marking the bark with my knife so I can find my way back.',
                 'I press on toward the hum in the ground.'):
        view = play.say(line)
        if view and (view.get('fight') or {}).get('fight'):
            break
    for line in ('I go for the nearest one with my sword, low and fast.',
                 'I hack at it again, putting my weight behind the swing.',
                 'I keep fighting, aiming for the throat.',
                 'I swing again.',
                 'I fight on.'):
        view = play.say(line)
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    play.journal()
    draft = play.back(3)
    play.say(draft)
    play.say('I turn back toward the stones before it gets worse.')


def brawl(play):
    """M1: starting a fight with a named person in town, morale and the defeat table, and death with going back."""
    play.start('tobin-pell')
    play.move('the-sawpit')
    play.say('I look around for the biggest logger in the place.')
    play.say('I throw my drink in his face and punch him.', {'fight': True})
    for line in ('I punch him again.', 'I kick at his knee.', 'I try to bite his ear.', 'I keep swinging.',
                 'I swing wildly.', 'I keep at it.'):
        view = play.say(line)
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    play.say('I pick myself up and check what I have left.')
    play.gear()
    play.say('I bandage my cuts as best I can.')
    play.say('I find somewhere quiet to sleep it off.')
    play.journal()


def road(play):
    """M2: travel with fog of war, road encounters, food, rest in the open and in town, wounds mending."""
    play.start('lirien-of-the-ford')
    play.say('OOC: where can my character travel from here?', {'no_roll': True})
    play.say('I set out for Convila along the forest road.', {'place': None})
    play.gear()
    play.say('I look around Convila and ask who is buying salt.')
    play.say('We make camp outside the town walls for the night, no fire, and I keep a watch.')
    play.say('I set out for the Abandoned Keep.')
    play.say('I make camp in the ruins for the night.')
    play.say('I search the ruins of the keep for anything worth carrying.')
    play.say('I take everything I found.')
    play.gear()
    play.sheet()
    play.say('I set out for Kingswood.')
    play.say('I rest for three days at the Wayhouse.')
    play.journal()


def director(play):
    """M2: days passing so factions, beats, Life Cards, jobs and the director move; looking for work; an oath."""
    play.start('agna-holt', hand='firm')
    play.say('I ask around the Felled Oak who is hiring, anything that pays.')
    play.say('I swear to the barkeep I will find out who leaves the arrows on the bunks, on my life, within three '
             'days.')
    for day in range(4):
        play.say('I sleep the night at the bunkhouses.')
        play.say('I spend the day felling trees in the stump fields and come back at dusk.')
    play.say('I go to the shrine and ask Mother Rook what lies under the Heartwood.')
    play.journal()
    play.people()


SCENARIOS = {'town': town, 'shop': shop, 'heartwood': heartwood, 'brawl': brawl, 'road': road,
             'director': director}
