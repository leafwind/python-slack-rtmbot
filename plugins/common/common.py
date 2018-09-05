# -*- coding: utf-8 -*-
crontable = []
#crontable.append([60*60, "drop_coin"])
outputs = []
import sqlite3
from pprint import pprint
import json
import random
import csv
import yaml
friend_await = {}
friend_sets = []
simple_unary_commands = json.load(open('simple_unary_commands.json'))
simple_binary_commands = json.load(open('simple_binary_commands.json'))
channel_map = {
    "general": "C0J4UTXL0",
    'bot-dev-test': 'C0JKD2HMM',
}

database = None
ADMIN = ''
slack = None

def get_all_users(channel_name):
    global slack
    all_users = []
    try:
        r = slack.sc.api_call("channels.info", channel=channel_map[channel_name])
    except Exception, e:
        import traceback
        traceback.print_exc()
        print "Couldn't do it: %s" % e
    if r["ok"] == True:
        all_users = r["channel"]["members"]
    return all_users

def get_active_users(channel_name):
    global slack
    active_users = []
    r = slack.sc.api_call("channels.info", channel=channel_map[channel_name])
    if r["ok"] == True:
        members = r["channel"]["members"]
        for user in members:
            r2 = slack.sc.api_call("users.getPresence", user=user)
            if r2["ok"] == True:
                if r2["presence"] == "away":
                    pass
                elif r2["presence"] == "active":
                    active_users.append(user)
    return active_users

def _drop_coin_target_users():
    global slack
    # all active users
    #users = get_active_users(slack, "general")
    # lucky user from active
    #users = random.choice(active_users)
    users = get_all_users(slack, "general")
    return users

def drop_coin():
    global slack
    drop_amount = 1
    target_users = _drop_coin_target_users()
    if len(target_users) == 0:
        return
    usernames = [slack.get_username(user) for user in target_users]
    usernames_at = ["@" + username for username in usernames]

    #slack.post_message("bot-dev-test", u"以下幸運兒獲得了 {} 塊金幣！\n {}".format(drop_amount, ", ".join(usernames_at)).encode('utf-8'), None)
    slack.post_message("bot-dev-test", u"所有人獲得了 {} 塊金幣！".format(drop_amount), None)

    conn = sqlite3.connect(database)
    c = conn.cursor()
    for user in usernames:
        c.execute('''INSERT OR REPLACE INTO coins (user, coins)
                     VALUES ( \'{}\', COALESCE((SELECT coins FROM coins WHERE user = \'{}\'), 0)
                     );'''.format(user, user))
        c.execute('''UPDATE coins SET coins = coins + {} WHERE user = \'{}\';'''.format(drop_amount, user))
    conn.commit()
    conn.close()

def flist(conn):
    c = conn.cursor()
    c.execute('''select user_a, user_b from friends''')
    result = c.fetchall()

    msg = []
    msg.append(u"貴圈真亂".encode('utf-8'))
    for row in result:
        msg.append("{} <=> {}".format(row[0], row[1]))
    return "\n".join(msg)

def freq(conn):
    c = conn.cursor()
    c.execute('''SELECT * from chat_freq order by count desc''')
    result = c.fetchall()
    msg = []
    msg.append(u"話多排行榜:".encode('utf8'))
    for row in result:
        msg.append("{}: {}".format(row[0], row[1]))

    c.execute('''SELECT * from cmd_freq order by count desc''')
    result = c.fetchall()
    msg.append(u"愛玩機器人排行榜".encode('utf-8'))
    for row in result:
        msg.append("{}: {}".format(row[0], row[1]))
    return "\n".join(msg)

def coins(user, conn):
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO coins (user, coins)
                 VALUES ( \'{}\', COALESCE((SELECT coins FROM coins WHERE user = \'{}\'), 0)
                 );'''.format(user['name'], user['name']))
    c.execute('''SELECT coins FROM coins WHERE user = \"{}\"'''.format(user['name']))
    result = c.fetchall()[0]
    coins = result[0]
    msg = u"<@{}|{}> 有 {} 個金幣。".format(user['id'], user['name'], coins).encode('utf-8')
    return msg

def sacrifice(user, channel_id):
    channelname = slack.get_channelname(channel_id)
    sacrifice_list = get_active_users(channelname)
    target = random.choice(sacrifice_list)
    r = slack.sc.api_call("users.info", user=target)
    target_user = r["user"]
    msg = u"<@{}|{}> 在此獻上:fire: <@{}|{}> :fire:為祭品──給我瞧仔細了！".format(user['id'], user['name'], target_user['id'], target_user['name'])
    return msg

def unary_command(cmd, channel_id, user, conn):
    global slack
    bot_icon = None
    if cmd[1:] in simple_unary_commands:
        msg = simple_unary_commands[cmd[1:]].format(user['name']).encode('utf-8')
    elif cmd in ['!flist']:
        msg = flist(conn)
    elif cmd in ['!freq']:
        msg = freq(conn)
    elif cmd in ["!coins"]:
        msg = coins(user, conn)
    elif cmd in ["!sacrifice"]:
        msg = sacrifice(user, channel_id)
    else:
        return
    slack.post_message(channel_id, msg, bot_icon)

def friend(user, target):
    global friend_await
    if user not in friend_await:
        friend_await[user] = []
    if target not in friend_await[user]:
        friend_await[user].append(target)
        msg = u"<@{}|{}> 想跟 <@{}|{}> 做朋友（輸入 !yfriend {} 同意）".format(user, target, user)
    else:
        msg = u"<@{}|{}> 人家還沒回應你在急屁急".format(user)
    return msg

def yfriend(user, target, conn):
    if target in friend_await:
        if user in friend_await[target]:
            c = conn.cursor()
            msg = u"<@{}|{}> 接受了 <@{}|{}> 的好友邀請，現在他們是好碰友".format(user, target)
            #friend_sets.append(set([user, target]))
            c.execute('''INSERT INTO friends (user_a, user_b) VALUES (\'{}\', \'{}\');'''.format(user, target))
            friend_await[target].remove(user)
            conn.commit()
        else:
            msg = u"<@{}|{}> 沒有想要跟你做朋友好ㄇ".format(target)
    else:
        msg = u"<@{}|{}> 沒有想要跟你做朋友好ㄇ".format(target)
    return msg

#def add_coins(user, coins, conn):
#    c = conn.cursor()
#    c.execute('''INSERT OR REPLACE INTO coins (user, coins)
#                 VALUES ( \'{}\', COALESCE((SELECT coins FROM coins WHERE user = \'{}\'), 0)
#                 );'''.format(user, user))
#    c.execute('''UPDATE coins SET coins = coins + {} WHERE user = \'{}\';'''.format(coins, user))
#    conn.commit()
#    msg = u"@{} 得到了 {} coins！".encode('utf-8').format(user, coins)
#    return msg

def add_coins_all(target, coins, conn):
    c = conn.cursor()
    for user in slack.user_info:
        c.execute('''INSERT OR REPLACE INTO coins (user, coins)
                     VALUES ( \'{}\', COALESCE((SELECT coins FROM coins WHERE user = \'{}\'), 0)
                     );'''.format(user, user))
        c.execute('''UPDATE coins SET coins = coins + {} WHERE user = \'{}\';'''.format(coins, user))
    conn.commit()
    msg = u"給所有人 {} coins！".encode('utf-8').format(coins)
    return msg

def binary_command(cmd, target, channel_id, user, conn):
    global slack
    bot_icon = None
    if cmd[1:] in simple_binary_commands:
        msg = simple_binary_commands[cmd[1:]].format(user['id'], user['name'], target).encode('utf-8')
    elif cmd in ["!add_coins_all"]:
        if user['name'] == ADMIN:
            coins = int(target)
            msg = add_coins_all(target, coins, conn)
        else:
            return
    elif cmd in ["!friend"]:
        msg = friend(user['name'], target)
    elif cmd in ["!yfriend"]:
        msg = yfriend(user['name'], target, conn)
    else:
        return
    slack.post_message(channel_id, msg, bot_icon)

def update_freq(text, user, conn):
    c = conn.cursor()
    if text.startswith('!'):
        freq_table = 'cmd_freq'
    else:
        freq_table = 'chat_freq'
    c.execute('''INSERT OR REPLACE INTO {} (user, count)
                 VALUES ( \'{}\',
                     COALESCE((SELECT count FROM {} WHERE user = \'{}\'), 0)
                 );'''.format(freq_table, user, freq_table, user))
    c.execute('''UPDATE {} SET count = count + 1 WHERE user = \'{}\';'''.format(freq_table, user))
    #c.execute('''SELECT * from {}'''.format(freq_table))
    #result = c.fetchall()
    #pprint(result)
    conn.commit()

def get_user_id(data):
    if data.get('username', '') == 'schubot':
        return None
    elif 'user' in data:
        return data['user']
    else:
        return None

def process_message(data, config={}):
    global ADMIN, database, slack
    slack = config.get('slack_client', None)
    ADMIN = config.get('ADMIN', '')
    database = config.get('database', None)
    channel_id = data['channel']
    channelname = slack.get_channelname(channel_id)
    user = {}
    user['id'] = get_user_id(data)
    if not user['id']:
        return

    conn = sqlite3.connect(database)
    c = conn.cursor()
    import pprint
    pprint.pprint(data)
    import sys
    sys.stdout.flush()
    if data['text'].startswith("!"):
        freq_table = 'cmd_freq'
    else:
        freq_table = 'chat_freq'
    c.execute('''create table if not exists {} (user TEXT PRIMARY KEY, count INT)'''.format(freq_table))
    c.execute('''create table if not exists friends (id INTEGER PRIMARY KEY AUTOINCREMENT, user_a TEXT, user_b TEXT, UNIQUE (user_a, user_b) ON CONFLICT IGNORE)''')
    c.execute('''create table if not exists coins (user TEXT PRIMARY KEY, coins INTEGER DEFAULT 0)''')
    c.execute('''create table if not exists pokemons (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, race INTEGER, level INTEGER, exp INTEGER, i_hp INTEGER, i_atk INTEGER, i_def INTEGER, i_satk INTEGER, i_sdef INTEGER, i_spd INTEGER)''')
    conn.commit()

    user['name'] = slack.get_username(user['id'])
    print("[general] msg: {} from username: {}, channel: {} ({})".format(data['text'].encode('utf8'), user['name'], channelname, channel_id))

    if data['text'].startswith("!"):
        msgs = data['text'].split(" ")
        if len(msgs) == 2:
            cmd = msgs[0]
            target = msgs[1]
            binary_command(cmd, target, channel_id, user, conn)
        elif len(msgs) == 1:
            cmd = msgs[0]
            unary_command(cmd, channel_id, user, conn)

    update_freq(data['text'], user['name'], conn)
    conn.close()
