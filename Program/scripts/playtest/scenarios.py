"""The playtest scenarios: the milestones' "done when" lists (docs/roadmap.md), played as a player would.

Each is a function of a `Play` (playtest.py). Lines are what a player types; `expect` adds checks.
"""
import json


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


def chapters(play):
    """M3: chapters closing at scene breaks and by hand, "Previously" openers, bookmarks, the branch tree, playing
    from a chapter, and the notebook."""
    play.start('agna-holt')
    play.say('I take a seat at the bar and ask the keeper what the town makes of the wardens.')
    play.say('I ask who in town has actually seen a warden, and where.')
    play.move('the-green')  # a new place is a scene break
    play.say('I read the contract notice and look for a crew boss to talk to.')
    play.attempt('End the chapter as "The notice"', 'POST', '/api/story/chapters/close', {'title': 'The notice'})
    play.say("I head to the guild factor's office to ask about signing on.")  # opens a chapter with "Previously"
    mark = play.lines()[-1]
    play.attempt('Bookmark that line', 'POST', '/api/story/bookmarks', {'message_id': mark['id'], 'name': 'Signing'})
    play.say('I sign my name in the ledger and ask when the first crew goes.')
    play.say('I sleep the night at the bunkhouses.')  # a rest is a scene break
    play.say('I get up, eat, and walk out to look at the stump fields.')
    listed = play.chapters().get('chapters') or []
    if len(listed) < 3:
        play.flag(f'Expected at least three chapters after a move, a hand-closed chapter and a rest; got {len(listed)}.')
    if listed and not any(chapter.get('title') == 'The notice' for chapter in listed):
        play.flag('The chapter named by hand did not keep its name.')
    if len(listed) >= 2:
        read = play.attempt('Read chapter 2', 'GET', f"/api/story/chapters/{listed[1]['id']}")
        play.write(f"- chapter 2 has {len((read or {}).get('lines') or [])} lines\n")
        play.attempt('Play from chapter 2', 'POST', f"/api/story/chapters/{listed[1]['id']}/back")
        play.say('I read the contract notice again, slowly this time, and count the names.')
    bookmarks = play.chapters().get('bookmarks') or []
    if bookmarks:
        play.attempt('Go to the bookmark', 'POST', f"/api/story/bookmarks/{bookmarks[0]['id']}/go")
        play.chapters()
    else:
        play.flag('The bookmark is not listed.')
    play.attempt('Write in the notebook', 'POST', '/api/story/notebook', {'text': 'Corin knows more than he says.'})
    notes = play.attempt('Read the notebook', 'GET', '/api/story/notebook') or {}
    if not notes.get('notes'):
        play.flag('The notebook note is not there.')


def ironman(play):
    """M3: Ironman, chosen at the start: no going back, telling a line again still allowed."""
    play.start('agna-holt', ironman=True)
    play.say('I ask the keeper for a room and a hot meal.')
    play.say('I ask him what the arrows on the bunks mean.')
    first = play.lines()[0]
    play.attempt('Go back in Ironman', 'POST', '/api/story/back', {'message_id': first['id']}, expect_refusal=True)
    play.attempt('Tell the last line again', 'POST', '/api/story/retry')
    if not play.chapters().get('ironman'):
        play.flag('The campaign does not say it is Ironman.')


def gm_view(play):
    """M3: the GM view: the whole record with hidden truth, Behind the story, feelings set by hand, asking again for
    one fact, adopted details and the director's seeds and beats."""
    play.dungeon.call('PUT', '/api/settings', {'gm_view': True})
    play.start('lirien-of-the-ford')
    play.say('I take a corner table at the Felled Oak and watch the room.')
    play.say('That woman in the good cloak by the cellar door: I watch her closely. Who is she waiting for?')
    play.say('I go over, sit across from her and ask her plainly what she wants in Kingswood.')
    play.say('I ask the keeper what he knows of the woman in the cloak.')
    people = play.gm().get('people') or []
    if people:
        play.attempt(f"Set {people[0].get('name')}'s trust by hand", 'PATCH',
                     f"/api/story/gm/people/{people[0].get('key')}", {'trust': 3, 'fear': 1})
    journal = play.journal()
    pulled = [entry for entry in journal.get('entries') or [] if entry.get('source') == 'narrator']
    if pulled:
        play.attempt(f"Ask again for the fact \"{pulled[0].get('text')}\"", 'POST',
                     f"/api/story/journal/{pulled[0]['id']}/regenerate")
    else:
        play.flag('No fact pulled from the story to ask again for.')
    play.write(f"- journal entries with the GM view on: {len(journal.get('entries') or [])}\n")
    for line in ('I go to the shrine and ask Mother Rook about the old trees.',
                 'I ask her what the wardens would do if one tree past the stones fell.',
                 'I leave and walk to the border stones at dusk, looking for anything left there.',
                 'I search the foot of the split stone.'):
        play.say(line)
    play.gm()


ERRANDS = ('I look over the stalls and buy nothing.', 'I ask a stallholder about the price of salt.',
           'I watch the carts come in from the Cyrel road.', 'I ask the cheese seller where she is from.',
           'I wander along the stalls and count the guild coats.', 'I ask a carter how the road is.',
           'I watch a boy steal an apple and say nothing.', 'I ask the knife grinder for the news.',
           'I sit on a barrel and watch the crowd thin.', 'I ask a woman with geese how much for one.',
           'I look for anyone selling ink.', 'I ask the ink seller what paper costs.',
           'I watch the light go on the stalls.', 'I ask the cheese seller if she will be here tomorrow.',
           'I go round the market once more.', 'I ask a guard what time the gate shuts.',
           'I stand by the well and drink.', 'I watch two boys fight over a dog.',
           "I ask the dog's owner its name.", 'I count the coins in my purse.',
           'I look at the sky for rain.', 'I ask the knife grinder about the factor.',
           'I watch the stallholders pack up.', 'I stretch my legs along the empty stalls.',
           'I wait a while by the well.', 'I ask a passing logger if the bunkhouses are full.')


def memory(play):
    """M3: layered recall and forgetting over a long session: the story so far folds into a summary, an early detail
    fades, and trying to remember it takes a Mind roll."""
    play.start('tobin-pell')
    play.say('I ask the keeper, Corin, the name of the ferryman at the ford, and what he looks like.')
    play.say('I thank him and ask what the ferryman charges for a crossing.')
    play.move('crossroads-market')
    for line in ERRANDS:
        play.say(line, {'max_words': 600})
    play.say('I try to remember the ferryman at the ford, what Corin told me about him.', {'roll': True})
    play.journal()


def legacy(play):
    """M3: export the story as a book and the campaign as a file, import it as a new world, and start a new story
    in another world with the old character as a villain."""
    play.start('tobin-pell')
    play.say('I tell the keeper I mean to skim the Guild one last time and leave town rich.')
    play.say('I sleep the night at the Wayhouse.')
    play.say("I go to the guild factor's office and take the week's tally ledger off the desk while the clerk is out.")
    play.attempt('End the chapter', 'POST', '/api/story/chapters/close', {'title': 'The last skim'})
    content = play.export()
    play.write(f"- worlds before import: {json.dumps(play.dungeon.call('GET', '/api/worlds'), ensure_ascii=False)[:600]}\n")
    if content:
        response = play.dungeon.http.post('/api/worlds/import', content=content)
        play.write(f'### Import the campaign as a new world: {response.status_code} {response.text[:300]}\n')
        if response.status_code not in (200, 201):
            play.flag(f'Campaign import failed: {response.status_code} {response.text[:200]}')
    made = play.attempt('Make a new world', 'POST', '/api/worlds', {'name': 'After Tobin'}) or {}
    play.write(f'- made: {json.dumps(made, ensure_ascii=False)[:600]}\n')
    new_id = made.get('id') or (made.get('world') or {}).get('id') or made.get('world_id')
    if not new_id:
        play.flag("Could not tell the new world's id from the response.")
        return
    play.attempt('Switch to the new world', 'POST', f'/api/worlds/{new_id}/switch')
    candidates = play.dungeon.call('GET', '/api/story/start').get('legacy') or []
    play.write(f'- legacy candidates: {json.dumps(candidates, ensure_ascii=False)[:600]}\n')
    if not candidates:
        play.flag('No legacy characters offered at the start of the new world.')
        return
    world_id = candidates[0].get('world_id') or candidates[0].get('id')
    play.start('agna-holt', legacy={'world_id': world_id, 'role': 'villain'})
    play.say('I ask the keeper whether anyone remembers a clerk called Tobin Pell.')
    play.say("I ask what became of the Guild's ledgers.")
    play.journal()


SCENARIOS = {'town': town, 'shop': shop, 'heartwood': heartwood, 'brawl': brawl, 'road': road,
             'director': director, 'chapters': chapters, 'ironman': ironman, 'gm_view': gm_view, 'memory': memory,
             'legacy': legacy}
