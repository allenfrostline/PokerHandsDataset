'''
INPUT:
The loop_tgz function below looks in the specified environment directory for all available files with a filename in
the format <game_type>.MMMMYY.tgz. This is a compressed "zip" file type that the loop_tgz function extracts into
uncompressed, readable files.

Each .tgz file extracts a "file group" of the following structure:
./<game_type>/MMMMYYY/hdb
./<game_type>/MMMMYYY/hroster
./<game_type>/MMMMYYY/pdb/pdb.player1 <- where "player1" is one player's username
./<game_type>/MMMMYYY/pdb/pdb.player2
./<game_type>/MMMMYYY/pdb/pdb.player3
...
./<game_type>/MMMMYYY/pdb/pdb.playerN

For the hand below, the various files have records that look like the following:
hdb file:

HAND INFORMATION (in hdb file)
------------------------------
timestamp      hand #     #players/starting potsize
         dealer    #play flop    turn    river  showdn     board
820830094  20  1163  2  2/20    2/40    2/80     2/80     Qc 4s 6s 5d 4d

ROSTER INFORMATION (in hroster file)
------------------------------------
820830094  2 Jak num

PLAYER INFORMATION (in pdb.* files)
-----------------------------------
player             #play prflop    turn         bankroll    winnings
          timestamp    pos   flop       river           action  cards
Jak       820830094  2  1 Bc  kc    kc    k          850   40   80 7c Ac
num       820830094  2  2 Bk  b     b     k         1420   40    0 9h Kh

In English, the database entry says that 2 players are at the table: "Jak" and "num".
Pre-flop, Jak makes a small blind (B) $5, num makes a big blind (B) $10, Jak calls (c), and
num checks (k).  The pot is $20 and we have 2 players.
The flop comes Qc 4s 6s, Jak checks (k), num bets (b) $10, Jak calls (c). The pot is now $40.
On the turn, 5d, Jak checks (k), num bets (b) $20, and Jak calls (c). The pot is now $80
On the river, 4d, Jak checks (k), and num checks (k). The pot remains $80.
At the showdown, Jak wins the hand with a pair of board 4's w/ Ace high versus num's board 4's w/ King high.
As a result, Jak wins the $80 pot.
Note that we don't know the cards of any players who fold before the showdown.
Also note that the format does not record exact bet amounts in pot-limit or no-limit, though
they can often be inferred from the total pot size after each round.


PROCESSING:
All valid hands found in the processed .tgz files are parsed into a list of "hands" dictionaries by running the
loop_file_groups function, which runs all of the following functions on each file group, one at a time:

- parse_hdb_file: parses the hdb file looking for a hand identifier, betting rounds, and board cards
- parse_hroster_file: parses the hroster file looking for each of the players that played each hand
- loop_pdb_files: loops through all of the pdb files in the pdb folder, identifying each one by the username on the end
    - parse_pdb_files: parses an individual pdb file, to determine what that player did with each hand she played
- append_hands_list_to_json_file: takes a list of all of the valid hands found in the file group, "dumps" them from
    Python dictionary format to JSON, and appends them to an output file, "cprg_hands.json"


OUTPUT:

A full element of the Python dictionary list that this code produces looks like this (from the example inputs above):

{'_id': 'holdem_199601_820830094',
 'board': ['Qc', '4s', '6s', '5d', '4d'],
 'dealer': 20,
 'game': 'holdem',
 'hand_num': 1163,
 'num_players': 2,
 'players': {'Jak': {'action': 40,
                     'bankroll': 850,
                     'bets': [{'actions': ['B', 'c'],
                                      'stage': 'p'},
                                     {'actions': ['k', 'c'],
                                      'stage': 'f'},
                                     {'actions': ['k', 'c'],
                                      'stage': 't'},
                                     {'actions': ['k'],
                                      'stage': 'r'}],
                     'pocket_cards': ['7c', 'Ac'],
                     'pos': 1,
                     'user': 'Jak',
                     'winnings': 80},
             'num': {'action': 40,
                     'bankroll': 1420,
                     'bets': [{'actions': ['B', 'k'],
                                      'stage': 'p'},
                                     {'actions': ['b'], 'stage': 'f'},
                                     {'actions': ['b'], 'stage': 't'},
                                     {'actions': ['k'],
                                      'stage': 'r'}],
                     'pocket_cards': ['9h', 'Kh'],
                     'pos': 2,
                     'user': 'num',
                     'winnings': 0}},
 'pots': [{'num_players': 2, 'stage': 'f', 'size': 20},
          {'num_players': 2, 'stage': 't', 'size': 40},
          {'num_players': 2, 'stage': 'r', 'size': 80},
          {'num_players': 2, 'stage': 's', 'size': 80}]}

The JSON file that gets produced has one of the above "hand" dictionaries per line, "dumped" into JSON format,
and ready for loading into MongoDB.
'''

# Parses "hdb" file from the IRC Poker Database http://poker.cs.ualberta.ca/irc_poker_database.html
from builtins import str
from ColorPrint import print
import os
from tarfile import TarFile
import re
import codecs
import json

# ENVIRONMENT VARIABLES -- CHANGE THESE TO FIT YOUR ENVIRONMENT
tgz_extract_directory = "/Users/allenfrostline/Downloads/"
OUTFILE = tgz_extract_directory + "hands.json"
LOCAL_OS = "mac"  # valid values are "mac" or "pc"
# END ENVIRONMENT VARIABLES

# Code to use the local_os variable to control logic
if LOCAL_OS == "mac":
    SLASH = "/"
else:
    SLASH = "\\"

# Global variables
pot_cats = ["f", "t", "r", "s"]  # f=flop, t=turn, r=river, s=showdown
deck = {
    'A': 'ace',
    'K': 'king',
    'Q': 'queen',
    'J': 'jack',
    'T': '10'
}  # No longer in use; here as a reference
suits = {
    'c': 'clubs',
    's': 'spades',
    'h': 'hearts',
    'd': 'diamonds'
}  # No longer in use; here as a reference
bet_action_codes = {
    '-': 'no action',
    'B': 'blind bet',
    'f': 'fold',
    'k': 'check',
    'b': 'bet',
    'c': 'call',
    'r': 'raise',
    'A': 'all-in',
    'Q': 'quits game',
    'K': 'kicked from game'
}
# bet_action_codes is no longer in use but here as a reference
bet_action_cats = ["p", "f", "t", "r"]  # p=pre-flop, f=flop, t=turn, r=river
folder_search_re = re.compile(r'\d{6}$', re.IGNORECASE)
tgz_search_re = re.compile(r'^\S*.\d{6}.tgz$', re.IGNORECASE)
valid_game_types = {
    "holdem", "holdem1", "holdem2", "holdem3", "holdemii", "holdempot",
    "nolimit", "tourney"
}


def parse_hdb_file(hdb_file, hands, invalid_keys):

    try:
        split_filename = hdb_file.split(SLASH)
        id_prefix = split_filename[-3] + "_" + split_filename[-2] + "_"
        with open(hdb_file, "r") as hdb:
            for line in hdb:
                hand = {}
                pot_data = []
                board = []
                line_parts = line.strip("\n").split(" ")
                line_parts = [elem for elem in line_parts if elem != '']
                _id = id_prefix + line_parts[0]
                hand["_id"] = _id
                hand["game"] = split_filename[-3]
                hand["dealer"] = int(line_parts[1])
                hand["hand_num"] = int(line_parts[2])
                hand["num_players"] = int(line_parts[3])
                for lp in line_parts[4:8]:
                    pot_data.append(lp)
                for card in line_parts[8:]:
                    board.append(card)

                pots = []
                i = 0
                for p in pot_data:
                    pot = {}
                    pot["stage"] = pot_cats[i]
                    if len(p.split("/")) == 2:
                        pot["num_players"] = int(p.split("/")[0])
                        pot["size"] = int(p.split("/")[1])
                    else:
                        invalid_keys.add(_id)
                    pots.append(pot)
                    i = i + 1
                ''' Old Code
                board = []
                for b in board_card_data:
                    board_card = {}
                    if b != "":

                        if board_card_data.index(b) + 1 <= 3:
                            board_card["stage"] = "flop"
                        elif board_card_data.index(b) + 1 == 4:
                            board_card["stage"] = "turn"
                        elif board_card_data.index(b) + 1 == 5:
                            board_card["stage"] = "river"
                        if b[0] in deck.keys():
                            board_card["value"] = deck[b[0]]
                        else:
                            board_card["value"] = b[0]
                        board_card["suit"] = suits[b[1]]
                        board.append(board_card)
                '''

                hand["pots"] = pots
                hand["board"] = board
                hands[_id] = hand
        hdb.close()
        return hands, id_prefix, invalid_keys

    except (KeyError, ValueError):
        invalid_keys.add(_id)
        hdb.close()
        return hands, id_prefix, invalid_keys


def parse_hroster_file(hroster_file, id_prefix, hands, invalid_keys):

    try:
        with open(hroster_file, "r") as hroster:
            for line in hroster:
                players = {}
                line_parts = line.strip("\n").split(" ")
                line_parts = [elem for elem in line_parts if elem != '']
                _id = id_prefix + line_parts[0]
                player_data = line_parts[2:]
                for p in player_data:
                    # If on pc replace "|" with "_" in the player's name
                    if LOCAL_OS == "pc":
                        p = re.sub(r'[|]', '_', p)
                    # end fix 1/4/16
                    player = {}
                    player["user"] = p
                    players[p] = player
                if _id in hands:
                    hands[_id]["players"] = players
                else:
                    invalid_keys.add(_id)
        hroster.close()
        return hands, invalid_keys

    except KeyError:
        invalid_keys.add(_id)
        hroster.close()
        return hands, invalid_keys


def parse_pdb_file(pdb_file, id_prefix, hands, invalid_keys):

    try:
        username = pdb_file.split(".")[-1]
        with open(pdb_file, "r") as pdb:
            for line in pdb:
                line_parts = line.strip("\n").split(" ")
                line_parts = [elem for elem in line_parts if elem != '']

                _id = id_prefix + line_parts[1]
                position = line_parts[3]

                bet_actions = []
                i = 0
                for item in line_parts:
                    bet_action = {}
                    bet_action["actions"] = []
                    if line_parts.index(item) >= 4 and line_parts.index(
                            item) <= 7:
                        for b in item:
                            bet_action["actions"].append(b)
                        bet_action["stage"] = bet_action_cats[i]
                        bet_actions.append(bet_action)
                        i = i + 1
                bankroll, action, winnings = line_parts[8:11]

                player_cards = []
                if len(line_parts) == 13:
                    for card in line_parts[11:13]:
                        player_cards.append(card)
                        ''' Old code
                        if item[0] in deck.keys():
                            player_card["value"] = deck[item[0]]
                        else:
                            player_card["value"] = item[0]
                        player_card["suit"] = suits[item[1]]
                        player_cards.append(player_card)
                        '''

                if _id in hands:
                    if _id not in invalid_keys:
                        if username in hands[_id]["players"]:
                            hands[_id]["players"][username][
                                "bets"] = bet_actions
                            hands[_id]["players"][username]["bankroll"] = int(
                                bankroll)
                            hands[_id]["players"][username]["action"] = int(
                                action)
                            hands[_id]["players"][username]["winnings"] = int(
                                winnings)
                            hands[_id]["players"][username][
                                "pocket_cards"] = player_cards
                            hands[_id]["players"][username]["pos"] = int(
                                position)
                        else:
                            invalid_keys.add(_id)
                else:
                    invalid_keys.add(_id)
        pdb.close()
        return hands, invalid_keys

    except IndexError:
        invalid_keys.add(_id)
        pdb.close()
        return hands, invalid_keys
    except KeyError:
        invalid_keys.add(_id)
        pdb.close()
        return hands, invalid_keys
    except ValueError:
        invalid_keys.add(_id)
        pdb.close()
        return hands, invalid_keys


def loop_pdb_files(pdb_file_directory, hands_col, id_prefix, invalid_keys):
    for root, dirs, files in os.walk(pdb_file_directory, topdown=False):
        for name in files:
            pdb_file = os.path.join(root, name)
            hs = parse_pdb_file(pdb_file, id_prefix, hands_col, invalid_keys)
    return hands_col, invalid_keys


def fix_players_list(hands_list):
    fixed_hands_list = []
    for h in hands_list:
        if "players" in h:
            players_list = list(h["players"].values())
            h["players"] = players_list
            fixed_hands_list.append(h)
    return fixed_hands_list


def loop_file_groups(file_groups):
    total_to_process = len(file_groups)
    i = 1
    running_total = 0
    for fg in file_groups:
        try:
            hands = {}
            hands_list = []
            invalid_keys = set()
            print("Processing " + fg + " (file group #" + str(i) + " of " + str(
                total_to_process) + ")")
            hdb_file = fg + "hdb"
            hroster_file = fg + "hroster"
            pdb_directory = fg + "pdb/"
            hands, idp, inv_keys = parse_hdb_file(hdb_file, hands, invalid_keys)
            hands, inv_keys = parse_hroster_file(hroster_file, idp, hands,
                                                 inv_keys)
            hands, inv_keys = loop_pdb_files(pdb_directory, hands, idp, inv_keys)
            hands = {key: hands[key] for key in hands if key not in inv_keys}
            hands_list = fix_players_list(list(hands.values()))
            append_hands_list_to_json_file(hands_list)
            print(str(len(hands_list)) + " valid hands added to JSON file, " + str(
                len(inv_keys)) + " invalid hands", color='green')
            running_total = running_total + len(hands_list)
            print(str(running_total) + " total hands added so far", color='yellow')
            print("Finished processing " + fg + '\n')
        except IndexError:
            print('Failed to process ' + fg + '\n')
        i = i + 1


def loop_tgz(extract_dir):
    try:
        file_groups = []
        for root, dirs, files in os.walk(tgz_extract_directory, topdown=False):
            for file in files:
                tgz = tgz_search_re.search(file)
                if tgz:
                    tgz_file = os.path.join(root, file)
                    game_type = tgz_file.split(".")[-3].split(SLASH)[-1]
                    file_yearmonth = tgz_file.split(".")[-2]
                    if game_type in valid_game_types:
                        print("Extracting " + tgz_file)
                        tar = TarFile.open(tgz_file)
                        if LOCAL_OS == "pc":
                            for f in tar:
                                # Replace "|" with "_".
                                f.name = re.sub(r'[|]', '_', f.name)
                        tar.extractall(extract_dir)
                        tar.close()
                        file_groups.append(tgz_extract_directory + game_type +
                                           SLASH + file_yearmonth + SLASH)
                    else:
                        print("Skipping " + tgz_file + " because it is for an invalid game type", color='red')
        return file_groups
    except IOError:
        # invalid_keys.add(_id)
        tar.close()
        return file_groups


def append_hands_list_to_json_file(hands_list):
    # db = connect_to_cloud_for_upload()
    with codecs.open(OUTFILE, "a") as fo:
        for hand in hands_list:
            fo.write(json.dumps(hand) + "\n")
    fo.close()


file_groups = loop_tgz(tgz_extract_directory)
print()
if os.path.isfile(OUTFILE): os.remove(OUTFILE)
loop_file_groups(file_groups)
print("Finished.")
