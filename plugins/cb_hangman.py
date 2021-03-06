#!/usr/bin/env python3

from random import choice
from carbonbot import Command


# Word selection stuff

with open('./hangman_words.txt', 'r') as _word_list_file:
    _WORD_LIST = tuple(map(lambda x: x.rstrip('\n').lower(),
                           _word_list_file.readlines()
                           ))


def candidate(word, pattern, previous_letters):
    return (
            # Length must be the same
            len(word) == len(pattern) and

            # All letters must either
            #  1) match and have been guessed or
            #  2) be blank and have not been guessed
            all((letter == pattern_char and letter in previous_letters) or (pattern_char == '_' and letter not in previous_letters)
                for letter, pattern_char in zip(word, pattern)
                )
            )


def fill(word, pattern, letter_to_reveal):
    return ''.join(letter if letter == letter_to_reveal else pattern_char
                   for letter, pattern_char in zip(word, pattern)
                   )


def select(pattern, previous_letters, guessed_letter):
    possible_patterns = {}
    best_option, best_option_possibilities = None, None

    for word in _WORD_LIST:
        if word and candidate(word, pattern, previous_letters):
            new_pattern = fill(word, pattern, guessed_letter)

            possibilities = possible_patterns.get(new_pattern)
            if possibilities is None:
                possible_patterns[new_pattern] = possibilities = []

            possibilities.append(word)

            if best_option_possibilities is None or len(possibilities) > len(best_option_possibilities):
                best_option, best_option_possibilities = new_pattern, possibilities

    # Return None when there are no fitting words in our word list
    if best_option is None:
        return None

    if len(best_option_possibilities) == 1 and '_' not in best_option:
        # If the best we can do is with only one word, try to find one that is not the solution, so that
        # >>> select('hell_', 'halgktes', 'o')
        # won't select "hello", it can choose "hell_" for "helly"
        better_option, better_option_possibilities = None, None
        for option, possibilities in possible_patterns.items():
            if '_' in option:
                better_option, better_option_possibilities = option, possibilities
                break

        # Select a valid pattern that's not the solution, but only if there is such a pattern
        if better_option is not None:
            best_option, best_option_possibilities = better_option, better_option_possibilities

    return (best_option, choice(best_option_possibilities))


# Chat driver stuff

TOLERANCE = 7

chat_games = {}

def chat_get_game(match, metadata, bot):
    adapter_id = metadata["_id"]
    channel = metadata["from_group"]

    if adapter_id not in chat_games:
        chat_games[adapter_id] = {}
        return None

    if channel not in chat_games[adapter_id]:
        return None

    return chat_games[adapter_id][channel]


def chat_new_game(match, metadata, bot):
    adapter_id = metadata["_id"]
    channel = metadata["from_group"]

    if adapter_id not in chat_games:
        chat_games[adapter_id] = {}

    word_len = len(choice(_WORD_LIST))
    game = {
        "word_len": word_len,
        "pattern": '_' * word_len,
        "previous_letters": set(),
        "misses_left": TOLERANCE
    }
    chat_games[adapter_id][channel] = game
    return game


def chat_end(match, metadata, bot):
    adapter_id = metadata["_id"]
    channel = metadata["from_group"]

    if channel in chat_games.get(adapter_id, {}):
        del chat_games[adapter_id][channel]


def chat_start(match, metadata, bot):
    game = chat_get_game(match, metadata, bot)

    if game:
        bot.send("Send a message consisting of one letter to make a guess.", metadata['from_group'], metadata['_id'])
    else:
        game = chat_new_game(match, metadata, bot)

        bot.reply("Started a new hangman game in English! The word is {word_len} letters long. Guess a letter…".format(word_len=game["word_len"]),
                 metadata['message_id'], metadata['from_group'], metadata['_id'])

    chat_status(match, metadata, bot)


def chat_guess(match, metadata, bot):
    game = chat_get_game(match, metadata, bot)

    if not game:
        if match['cmd']:
            bot.reply("There's no hangman game going on here! Start one first by doing !hangman", metadata['message_id'],
                      metadata['from_group'], metadata['_id'])
        return

    guessed_letter = match["letter"].lower()
    if guessed_letter == "_":
        bot.reply("No words contain underscores. Lol, that'd be confusing.", metadata['message_id'], metadata['from_group'], metadata['_id'])
        chat_status(match, metadata, bot)
        return

    if guessed_letter in game["previous_letters"]:
        bot.reply(("You already guessed {letter}"
                   if guessed_letter in game["pattern"]
                   else "You already tried {letter}"
                   ).format(letter=guessed_letter.upper()),
                  metadata['message_id'], metadata['from_group'], metadata['_id'])
        return

    selection = select(game["pattern"], game["previous_letters"], guessed_letter)
    if selection is None:
        bot.reply("Sorry, something went wrong!", metadata['message_id'], metadata['from_group'], metadata['_id'])
        chat_end(match, metadata, bot)
        return

    game["pattern"], matching_word = selection
    game["previous_letters"].add(guessed_letter)
    if guessed_letter not in game["pattern"]:
        game["misses_left"] -= 1

    if '_' not in game["pattern"]:
        # Guessed the word!
        chat_status(match, metadata, bot)
        chat_end(match, metadata, bot)
        bot.reply("Congratulations, you guessed the word!", metadata['message_id'], metadata['from_group'], metadata['_id'])
        return

    if not game["misses_left"]:
        chat_status(match, metadata, bot)
        chat_end(match, metadata, bot)
        bot.reply("Game over! The word was {}.".format(matching_word.upper()), metadata['message_id'], metadata['from_group'], metadata['_id'])
        return

    chat_status(match, metadata, bot)

def chat_status(match, metadata, bot):
    game = chat_get_game(match, metadata, bot)

    bot.send('{pattern}   {left}/{total}'.format(pattern=" ".join(game["pattern"].upper()),
                                               left=game["misses_left"],
                                               total=TOLERANCE
                                               ),
             metadata['from_group'], metadata['_id']
             )


def register_with(carbon):
    carbon.add_commands(
        Command(r"{ident}hangman(?: .*)?",
                "hangman",
                "Play a game of hangman: guess a word one letter at a time",
                chat_start
                ),
        Command(r"(?P<cmd>{ident}guess )?(?P<letter>[A-Za-z_])",
                "", "",
                chat_guess,
                display_condition = lambda message, metadata, bot: False,
                ),
    )
