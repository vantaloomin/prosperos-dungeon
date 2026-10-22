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
    play.start('lirien-of-the-ford', table={'gm_view': True})
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


def fivee_checks(play):
    """M4: a made 5E character (class, species, background, the standard array, skills): skill checks against DCs,
    a haggle, and the sheet."""
    choices = play.dungeon.call('GET', '/api/story/start')
    srd = choices.get('srd52') or {}
    classes = {item['id']: item for item in srd.get('classes') or []}
    if 'rogue' not in classes or not srd.get('backgrounds'):
        play.flag(f"No 5E rogue or backgrounds offered: {sorted(classes)}")
        return
    rogue, background = classes['rogue'], srd['backgrounds'][0]
    ids = {skill['name']: skill['id'] for skill in srd.get('skills') or []}
    taken = set(background.get('skills') or [])
    picks = [ids.get(name, name) for name in rogue['skills']['from'] if name not in taken]
    play.start(persona={'name': 'Maren Voss', 'gender': 'woman', 'age': 27,
                        'about': 'A lockpick from Cyrel who came north owing the wrong people.'},
               ruleset='srd52', build={'class_id': 'rogue', 'species_id': 'human', 'background_id': background['id'],
                                       'scores': {'dex': 15, 'int': 14, 'con': 13, 'wis': 12, 'cha': 10, 'str': 8},
                                       'skills': picks[:rogue['skills']['count']]})
    play.sheet()
    play.say('I climb the back wall of the Felled Oak to the shuttered window above the cellar door.', {'roll': True})
    play.say('I pick the lock on the shutter, quiet as I can.', {'roll': True})
    play.say('I listen at the door of the room beyond for anyone awake.', {'roll': True})
    play.move('pell-provisions')
    play.say('I haggle over a coil of rope, all charm and a sad story.', {'roll': True})
    play.say('I lie to the keeper that the Guild sent me to check her scales.', {'roll': True})
    play.gear()


def fivee_fight(play):
    """M4: 5E fights: SRD stat blocks, attacks on AC, hit points, death saves, and going back."""
    play.start('agna-holt', ruleset='srd52')
    play.sheet()
    play.move('the-heartwood')
    for line in ('I push into the Heartwood along the old trail, sword drawn.',
                 'I go deeper, toward the oldest trees.',
                 'I keep going, marking the bark as I go.',
                 'I press on toward the hum in the ground.',
                 'I go on, slow and watchful.'):
        view = play.say(line)
        if view and (view.get('fight') or {}).get('fight'):
            break
    for line in ('I attack the nearest one with my sword.', 'I attack again, putting my weight behind it.',
                 'I keep fighting.', 'I swing at whoever is still standing.', 'I fight on.', 'I fight on.'):
        view = play.say(line)
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    if (play.story().get('fight') or {}).get('dead'):
        # Dead in the Heartwood: back to before the woods so the brawl can still be played.
        play.back(next(n for n, line in enumerate(reversed(play.lines()), 1) if 'Heartwood' in line['text']))
        play.say('I turn round and head back to town instead.')
    play.move('the-sawpit')
    play.say('I look for the biggest logger in the place.')
    play.say('I punch him in the jaw.', {'fight': True})
    play.say('I hit him again.')
    draft = play.back(2)
    play.say(draft)


def fivee_caster(play):
    """M4: a 5E wizard: cantrips and prepared spells, slots spent and failing when gone, spell attacks in a fight,
    XP for a won fight, and a long rest giving the slots back."""
    srd = play.dungeon.call('GET', '/api/story/start').get('srd52') or {}
    background = next((item for item in srd.get('backgrounds') or [] if item['id'] == 'sage'),
                      (srd.get('backgrounds') or [{}])[0])
    wizard = next(item for item in srd.get('classes') or [] if item['id'] == 'wizard')
    ids = {skill['name']: skill['id'] for skill in srd.get('skills') or []}
    picks = [ids.get(name, name) for name in wizard['skills']['from'] if name not in (background.get('skills') or [])]
    play.start(persona={'name': 'Oriel Fenn', 'gender': 'man', 'age': 34,
                        'about': 'A hedge scholar from Eriane who reads ley lines for the Guild and lies about it.'},
               ruleset='srd52', build={'class_id': 'wizard', 'species_id': 'human', 'background_id': background['id'],
                                       'scores': {'int': 15, 'con': 14, 'dex': 13, 'wis': 12, 'cha': 10, 'str': 8},
                                       'skills': picks[:wizard['skills']['count']]})
    sheet = play.sheet()
    spells = sheet.get('spells') or {}

    def spoken(spell_id: str) -> str:
        return spell_id.replace('-', ' ').title()

    cantrips = [spoken(spell) for spell in spells.get('cantrips') or []]
    levelled = [spoken(spell) for spell in spells.get('prepared') or []]
    play.write(f"- cantrips {cantrips}; prepared {levelled}; slots {spells.get('slots')}\n")
    if not cantrips:
        play.flag('The wizard has no cantrips on the sheet.')
        return
    cantrip = next((name for name in cantrips if name == 'Fire Bolt'), cantrips[0])
    play.say(f'I cast {cantrip} at the empty bottle on the fence post outside.', {'roll': True})
    # Two first-level slots: the third cast should fail for want of one.
    for _ in range(3):
        if levelled:
            play.say(f'I cast {levelled[0]} at the scarecrow in the stump field.')
    names = [cantrip]
    play.sheet()
    play.move('the-heartwood')
    for line in ('I walk into the Heartwood, reading the ley in the bark.', 'I go deeper toward the hum.',
                 'I keep going, slow, a spell ready.', 'I press on.'):
        view = play.say(line)
        if view and (view.get('fight') or {}).get('fight'):
            break
    for _ in range(5):
        view = play.say(f'I cast {names[0]} at the nearest one.')
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    play.move('the-wayhouse')
    play.say('I sleep the night at the Wayhouse.')
    play.sheet()


def ironsworn(play):
    """M4: an Ironsworn character (3, 2, 2, 1, 1 and three assets): moves read from the words, the action roll with
    momentum, a fight with a thug on health and harm, a day's travel, the Heartwood contract as a vow, and rest."""
    choices = play.dungeon.call('GET', '/api/story/start').get('ironsworn') or {}
    stats = [stat['id'] for stat in choices.get('stats') or []]
    assets = choices.get('assets') or []
    if len(stats) != 5 or len(assets) < 3:
        play.flag(f'Ironsworn choices look wrong: stats {stats}, {len(assets)} assets.')
        return
    placed = dict(zip(('iron', 'edge', 'wits', 'heart', 'shadow'), choices.get('array') or [3, 2, 2, 1, 1]))
    by_category = {}
    for asset in assets:
        by_category.setdefault(asset['category'], asset['id'])
    picks = list(by_category.values())[:choices.get('count') or 3]
    play.start(persona={'name': 'Hald Brenner', 'gender': 'man', 'age': 41,
                        'about': 'A sworn sword out of Bastion who keeps his oaths and little else.'},
               ruleset='ironsworn', ironsworn={'stats': placed, 'assets': picks})
    play.sheet()
    play.say('I ask the keeper who in Kingswood needs a sword they can trust.')
    play.say('I search the notice post on the green for anything about the Heartwood.')
    play.say('I talk the factor round to telling me the truth about the double wages.', {'roll': True})
    play.say('I swear an iron vow to see the Heartwood contract through, whatever it costs, and I mean it.')
    play.move('the-sawpit')
    play.say('I pick out the loudest thug in the room.')
    play.say('I shove him off his stool and hit him.', {'fight': True})
    for line in ('I hit him again.', 'I keep at him.', 'I finish it.', 'I fight on.'):
        view = play.say(line)
        if not ((view or {}).get('fight') or {}).get('fight'):
            break
    play.sheet()
    if (play.story().get('fight') or {}).get('dead'):
        # Dead in a bar brawl: go back to before the fight so the rest of the scenario can play.
        play.back(next(n for n, line in enumerate(reversed(play.lines()), 1) if 'shove him' in line['text']))
    play.say('I set out for Convila along the forest road.')
    play.sheet()
    play.say('I make camp outside the walls for the night and keep a watch.')
    play.sheet()
    play.journal()


def percentile(play):
    """M4: a Percentile (BRP) character bought on the start screen: skill rolls named by the words, experience checks
    after a night's rest, a fight with weapon skills and dodge, wounds, First Aid and slow healing."""
    choices = play.dungeon.call('GET', '/api/story/start').get('brp') or {}
    if not choices.get('professions'):
        play.flag('No Percentile professions offered.')
        return
    # 24 points over 10s, DEX, INT and POW at 3 a point: STR 16, CON 14, SIZ 13, CHA 12, DEX 12, INT 11, POW 10.
    play.start(persona={'name': 'Sefa Dunmore', 'gender': 'woman', 'age': 32,
                        'about': 'A sell-sword who came north with a Cyrel caravan and stayed for the wages.'},
               ruleset='brp', brp={'characteristics': {'str': 16, 'con': 14, 'siz': 13, 'cha': 12, 'dex': 12,
                                                       'int': 11, 'pow': 10},
                                   'profession': 'warrior', 'personality': 'brutal'})
    before = play.sheet()
    play.say('I climb onto the Felled Oak roof to see over the town.', {'roll': True})
    play.say('I look about the square for anyone watching me.', {'roll': True})
    play.move('pell-provisions')
    play.say('I haggle over a whetstone, hard.', {'roll': True})
    play.say('I sleep the night at the Wayhouse.')
    after = play.sheet()
    if json.dumps(before.get('skills'), sort_keys=True) == json.dumps(after.get('skills'), sort_keys=True):
        play.write('- no skill rose from the experience checks this night\n')
    play.move('the-sawpit')
    play.say('I pick out the biggest bruiser in the room.')
    play.say('I draw my sword and go for him.', {'fight': True})
    for line in ('I dodge his swing and cut at him.', 'I attack again.', 'I keep fighting.', 'I fight on.'):
        view = play.say(line)
        if not ((view or {}).get('fight') or {}).get('fight'):
            break
    play.sheet()
    if (play.story().get('fight') or {}).get('dead'):
        play.back(next(n for n, line in enumerate(reversed(play.lines()), 1) if 'draw my sword' in line['text']))
        play.say('I let him be and drink instead.')
    for _ in range(3):
        if not (play.story().get('fight') or {}).get('fight'):
            break
        play.say('I break away and run for the door.')
    play.say('I climb the Sawpit stairs two at a time and look about for anyone following.')
    hurt = (play.story().get('fight') or {}).get('hp', 0) < (play.story().get('fight') or {}).get('max_hp', 0)
    view = play.say('I bind my wounds with a strip of my shirt.', {'roll': hurt})
    rolled = [roll for m in (view or {}).get('messages') or [] if m['role'] == 'user' for roll in m.get('rolls') or []]
    if hurt and not any('First Aid' in (roll.get('skill') or '') for roll in rolled[-2:]):
        play.flag('Binding a real wound did not roll First Aid.')
    play.say('I sleep three nights at the Wayhouse to heal.')
    play.sheet()


def lore(play):
    """M5: a fresh Vallarith campaign carries the world package's lore book, and naming a place pulls in its entry."""
    play.start('agna-holt')
    books = play.dungeon.call('GET', '/api/lore')
    names = [book.get('name') or book.get('title') for book in (books.get('books') if isinstance(books, dict) else books)
             or []]
    play.write(f'- lore books: {names}\n')
    if not any('world package' in (name or '') for name in names):
        play.flag(f'No "(world package)" lore book on a fresh Vallarith campaign: {names}')
    view = play.say('I ask the keeper what news there is from Dun Aldun, and whether the dwarves still sell their '
                    'steel south.')
    told = next((m['text'] for m in reversed((view or {}).get('messages') or []) if m['role'] == 'narrator'), '')
    if 'Stoneheart' not in told and 'dwar' not in told.lower():
        play.flag('The narration about Dun Aldun shows nothing from its lore entry.')
    play.say('I ask what the Kingdom of Cyrel and the High Elves of Brynwyr are to each other these days.')


def narrative(play):
    """M4: Narrative Only: the About text is the sheet; a judge rules No, No but, Yes but or Yes from who the character
    is, the words and how people feel. An unlikely seduction by an ill-suited character, then plausible actions."""
    play.start(persona={'name': 'Osric Vell', 'gender': 'man', 'age': 52,
                        'about': 'A stooped, nervous bookkeeper with ink-black fingers, a wheeze and a bad wig. '
                                 'He has never once been flirted with and would not know it if he were.'},
               ruleset='narrative', narrative={'good_at': ['sums and ledgers', 'noticing a cooked book'],
                                              'bad_at': ['talking to strangers', 'anything physical']},
               table={'gm_view': True})
    play.sheet()
    play.say("I lean across the bar and seduce the keeper with a slow, smouldering look and a line about her eyes.",
             {'roll': True})
    play.say('I try again, bolder, and ask her up to my room.', {'roll': True})
    play.move('guild-factor')
    play.say('I ask to see the week\'s tally ledger and check its sums for anything cooked.', {'roll': True})
    play.say('I vault the counter and wrestle the clerk for the key to the chest.', {'roll': True})
    play.say('I explain politely that I am a bookkeeper and offer to balance their accounts for a fee.')


def fivee_defeat(play, rule: str):
    """A fragile 5E wizard in the Heartwood until a fight takes them down: under `rule`, how the defeat lands."""
    srd = play.dungeon.call('GET', '/api/story/start').get('srd52') or {}
    wizard = next(item for item in srd.get('classes') or [] if item['id'] == 'wizard')
    background = next((item for item in srd.get('backgrounds') or [] if item['id'] == 'sage'), srd['backgrounds'][0])
    ids = {skill['name']: skill['id'] for skill in srd.get('skills') or []}
    picks = [ids.get(name, name) for name in wizard['skills']['from'] if name not in (background.get('skills') or [])]
    play.start(persona={'name': 'Ivo Marsh', 'gender': 'man', 'age': 24, 'about': 'A hedge wizard, short of breath.'},
               ruleset='srd52', table={'defeat': rule},
               build={'class_id': 'wizard', 'species_id': 'human', 'background_id': background['id'],
                      'scores': {'int': 15, 'con': 8, 'dex': 13, 'wis': 12, 'cha': 10, 'str': 14},
                      'skills': picks[:wizard['skills']['count']]})
    play.move('the-heartwood')
    for _ in range(24):
        view = play.say('I go deeper into the Heartwood.') if not ((play.story().get('fight') or {}).get('fight')) \
            else play.say('I swing my staff at the nearest one.')
        state = (view or play.story()).get('fight') or {}
        if state.get('dead') or state.get('captors'):
            break
    final = play.story().get('fight') or {}
    play.write(f"- after the fight: dead {final.get('dead')}, captors {final.get('captors')}\n")
    return final


def fivee_defeat_aim(play):
    """M4: 5E with "Foes decide a defeat" on: wardens who want the character taken take them prisoner."""
    final = fivee_defeat(play, 'by_aim')
    if final.get('dead') and 'warden' in json.dumps(play.story().get('fight') or {}):
        play.flag('Under "Foes decide a defeat", wardens who want capture killed the character.')
    if final.get('captors') and final.get('injuries'):
        play.flag(f"The captors maimed the character they took: {final.get('injuries')}")


def fivee_defeat_written(play):
    """M4: 5E with the defeat as written: death saves run whatever the foes want."""
    fivee_defeat(play, 'as_written')


def importer(play):
    """M5: the world importer: two documents and a lorebook become a draft; a section drafted by the model, reviewed
    and approved; the package written and listed."""
    files = [{'name': 'overview.md', 'text': (
                 '# The Saltmarch\n\nA drowned coast of reed islands under the rule of the Tidewardens, a council '
                 'of seven families who own every causeway. Salt and eels are the only trade. The town of Brackwater '
                 'sits on the largest island; the hamlet of Low Reed on the edge of the open sea. Inland lies the '
                 'Mire of Ash, where nobody goes. The Tidewardens secretly pay the Mire\'s witch for calm weather.')},
             {'name': 'people.md', 'text': (
                 '# People\n\n- Marra Quill, eldest Tidewarden, keeps the causeway tolls.\n- Fenwick, a salt boiler in '
                 'Low Reed who smuggles eels past the tolls.\n- The Mire witch, never named, owed a child every '
                 'seventh winter.')},
             {'name': 'saltmarch-lore.json', 'text': json.dumps({'entries': {
                 '0': {'key': ['causeway', 'causeways'], 'content': 'The causeways flood at spring tide; crossing '
                       'without a Tidewarden token costs a silver penny.'},
                 '1': {'key': ['eel', 'eels'], 'content': 'Saltmarch eels are smoked over reed fires and sold '
                       'south by the barrel.'}}})}]
    draft = play.attempt('Start a world import', 'POST', '/api/packages/drafts', {'name': 'The Saltmarch',
                                                                                   'files': files}) or {}
    draft_id = draft.get('id') or (draft.get('draft') or {}).get('id')
    play.write(f'- draft: {json.dumps(draft, ensure_ascii=False)[:800]}\n')
    lore_titles = [entry.get('title') for item in draft.get('sections') or [] if item.get('id') == 'lore'
                   for entry in item.get('entries') or []]
    if any((title or '').startswith('Entry ') for title in lore_titles):
        play.flag(f'Lorebook entries are titled by number, not by their keywords: {lore_titles}')
    if not draft_id:
        play.flag('No draft id from the import.')
        return
    play.attempt('Approve the lorebook as the lore section', 'PUT', f'/api/packages/drafts/{draft_id}/sections/lore',
                 {'status': 'approved'})
    for section in ('regions', 'settlements', 'cast'):
        drafted = play.attempt(f'Draft {section} with the model', 'POST',
                               f'/api/packages/drafts/{draft_id}/sections/{section}/draft') or {}
        found = next((item for item in drafted.get('sections') or [] if item.get('id') == section), {})
        play.write(f"- {section}: {json.dumps(found.get('entries'), ensure_ascii=False)[:900]}\n")
        if not found.get('entries'):
            play.flag(f'The model drafted no {section}.')
        play.attempt(f'Approve {section}', 'PUT', f'/api/packages/drafts/{draft_id}/sections/{section}',
                     {'status': 'approved'})
    view = play.attempt('Read the draft', 'GET', f'/api/packages/drafts/{draft_id}') or {}
    play.write(f'- draft now: {json.dumps(view, ensure_ascii=False)[:1200]}\n')
    finished = play.attempt('Write the package', 'POST', f'/api/packages/drafts/{draft_id}/finish', {})
    play.write(f'- finished: {json.dumps(finished, ensure_ascii=False)[:600]}\n')
    listed = play.dungeon.call('GET', '/api/packages')
    names = json.dumps(listed, ensure_ascii=False)
    if 'Saltmarch' not in names:
        play.flag('The imported world is not listed among the packages.')
    play.write(f'- packages: {names[:800]}\n')


def editor(play):
    """M5: the world editor on a built-in world: find an entry, edit it, see a bad edit refused, undo, edit again and
    play it, then reset the world to how it shipped."""
    base = '/api/packages/vallarith'
    found = play.attempt('Search the lore for Dun Aldun', 'GET', f'{base}/entries?section=lore&q=Dun%20Aldun') or {}
    play.write(f'- search: {json.dumps(found, ensure_ascii=False)[:700]}\n')
    entry_id = next((hit['id'] for hit in found.get('entries') or [] if hit.get('section') == 'lore'), None)
    if not entry_id:
        play.flag('No lore entry found for Dun Aldun.')
        return
    shown = play.attempt('Open the entry', 'GET', f'{base}/entries/lore/{entry_id}') or {}
    entry = shown.get('entry') or shown
    play.write(f'- entry: {json.dumps(entry, ensure_ascii=False)[:600]}\n')
    original = entry.get('text', '')
    edited = dict(entry, text=original + ' Since the spring, the Stoneheart Clan sells its steel only through Mordun, '
                                          'and only for silver weighed on dwarven scales.')
    play.attempt('Save an edit', 'PUT', f'{base}/entries/lore/{entry_id}', {'entry': edited})
    play.attempt('Save a bad id', 'PUT', f'{base}/entries/lore/{entry_id}', {'entry': dict(entry, id='Not Kebab Case')},
                 expect_refusal=True)
    play.attempt('Undo', 'POST', f'{base}/undo')
    after = (play.attempt('Read it back', 'GET', f'{base}/entries/lore/{entry_id}') or {})
    if (after.get('entry') or after).get('text') != original:
        play.flag('Undo did not restore the entry as it was.')
    play.attempt('Save the edit again', 'PUT', f'{base}/entries/lore/{entry_id}', {'entry': edited})
    history = play.attempt('Read the history', 'GET', f'{base}/history') or {}
    play.write(f"- history entries: {len(history.get('history') or [])}\n")
    play.start('agna-holt')
    view = play.say('I ask the keeper how a body buys dwarven steel these days, and from where.')
    told = next((m['text'] for m in reversed((view or {}).get('messages') or []) if m['role'] == 'narrator'), '')
    play.write(f"- the edit on the page: {'silver' in told.lower() and 'mordun' in told.lower()}\n")
    reset = play.attempt('Reset the built-in world', 'POST', f'{base}/reset') or {}
    play.write(f'- after reset: {json.dumps(reset, ensure_ascii=False)[:300]}\n')
    back = play.attempt('Read the entry after reset', 'GET', f'{base}/entries/lore/{entry_id}') or {}
    if (back.get('entry') or back).get('text') != original:
        play.flag('Reset did not bring the entry back as it shipped.')


SCENARIOS = {'town': town, 'shop': shop, 'heartwood': heartwood, 'brawl': brawl, 'road': road,
             'director': director, 'chapters': chapters, 'ironman': ironman, 'gm_view': gm_view, 'memory': memory,
             'legacy': legacy, 'fivee_checks': fivee_checks, 'fivee_fight': fivee_fight,
             'fivee_caster': fivee_caster, 'ironsworn': ironsworn, 'percentile': percentile,
             'lore': lore, 'narrative': narrative, 'fivee_defeat_aim': fivee_defeat_aim,
             'fivee_defeat_written': fivee_defeat_written, 'importer': importer,
             'editor': editor}
