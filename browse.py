from ColorPrint import GREEN, RED, RESET
from pprint import pprint
import json


try:
    with open('hands_valid.json', 'r') as f:
        print('#' * 60)
        line = f.readline()
        while line:
            hand = json.loads(line)
            print('{}{:>7}{} : {}'.format(GREEN, 'time', RESET, hand['time']), end='')
            print('{}{:>14}{} : {}'.format(GREEN, 'id', RESET, hand['id']))
            print('{}{:>7}{} : {}'.format(GREEN, 'board', RESET, hand['board']))
            print('{}{:>7}{} : '.format(GREEN, 'pots', RESET), end='')
            pots = []
            for stage in ['f', 't', 'r', 's']:
                p = [h for h in hand['pots'] if h['stage'] == stage][0]
                pots.append((p['num_players'], p['size']))
            print(pots)
            print('{}{:>7}{} : '.format(GREEN, 'players', RESET))
            hand['players'] = {player['pos']: player for player in hand['players']}
            for pos in range(1, hand['num_players'] + 1):
                description = hand['players'][pos].copy()
                user = description['user']
                del description['user'], description['pos']
                print('{}{:^60}{}'.format(RED, user + ' (#' + str(pos) + ')', RESET))
                pprint(description)
                print(('· ' if pos < hand['num_players'] else '##') * 30)
            line = f.readline()
    print('Finished.')
except KeyboardInterrupt:
    print('Interrupted.')
