import sqlite3 as db
import datetime as dt

test_db = "test_tracking"
db_name = "tracking"
winner_table = "Winners"
player_table = "Players"
deck_table = "Decks"
turns_table = "Turns"
games_table = "Games"


def connect(is_test):
    if is_test:
        return db.connect(test_db)
    else:
        return db.connect(db_name)


def create_all_tables(is_test):
    create_winner_table(is_test)
    create_player_table(is_test)
    create_deck_table(is_test)
    create_turns_table(is_test)
    create_games_table(is_test)


def create_player_table(is_test):
    try:
        conn = connect(is_test)
        conn.cursor().execute(
            """CREATE TABLE {t}
            (name TEXT,
            win_rate REAL,
            games NUMBER)""".format(
                t=player_table
            )
        )
    except db.OperationalError as e:
        print(e)
    finally:
        conn.close()


def create_deck_table(is_test):
    try:
        conn = connect(is_test)
        conn.cursor().execute(
            """CREATE TABLE {t}
            (name TEXT,
            owner TEXT,
            win_rate REAL,
            turn_win_ave REAL,
            games NUMBER)""".format(
                t=deck_table
            )
        )
    except db.OperationalError as e:
        print(e)
    finally:
        conn.close()


def create_winner_table(is_test):
    try:
        conn = connect(is_test)
        conn.cursor().execute(
            """CREATE TABLE {t}
            (winner TEXT,
            decks TEXT,
            position INTEGER,
            style TEXT,
            turns INTEGER,
            date DATE, 
            win_con TEXT,
            win_details TEXT,
            game_id NUMBER)""".format(
                t=winner_table
            )
        )
    except db.OperationalError as e:
        print(e)
    finally:
        conn.close()


def create_turns_table(is_test):
    try:
        conn = connect(is_test)
        conn.cursor().execute(
            """CREATE TABLE {t}
            (game_id NUMBER,
            round NUMBER,
            player_turn TEXT,
            turn_events TEXT)""".format(
                t=turns_table
            )
        )
    except db.OperationalError as e:
        print(e)
    finally:
        conn.close()


def create_games_table(is_test):
    try:
        conn = connect(is_test)
        conn.cursor().execute(
            """CREATE TABLE {t}
            (game_id NUMBER,
             player_name TEXT,
             deck_name TEXT,
             order_position NUMBER)""".format(
                t=games_table
            )
        )
    except db.OperationalError as e:
        print(e)
    finally:
        conn.close()


def insert_into_player(full_name, is_test):
    try:
        conn = connect(is_test)
        conn.cursor().execute(
            """INSERT INTO {t} (name, win_rate, games)
            VALUES('{fn}', 0.0, 1)""".format(
                t=player_table, fn=full_name
            )
        )
        conn.commit()
    finally:
        conn.close()


def merge_into_player(is_test, full_name):
    try:
        conn = connect(is_test)
        c = conn.cursor()
        rows = c.execute("""
        SELECT games FROM {t} WHERE name = '{fn}'""".format(t=player_table, fn=full_name)).fetchall()
        if len(rows) > 0:
            c.execute("""
            UPDATE {} SET games = {}, win_rate = {} WHERE name = '{}'""".format(player_table, rows[0][0]+1,
                                                                                calculate_player_win_rate(is_test, full_name),
                                                                                full_name))
            conn.commit()
        else:
            insert_into_player(full_name, is_test)
    finally:
        conn.close()


def get_players(is_test):
    player_names = []
    try:
        conn = connect(is_test)
        c = conn.cursor()
        rows = c.execute(
            """SELECT name
            FROM {t}""".format(
                t=player_table
            )
        ).fetchall()
        for row in rows:
            player_names.append(row[0])
        return player_names
    finally:
        conn.close()


def insert_into_deck_table(deck_name, deck_owner, is_test):
    try:
        conn = connect(is_test)
        conn.cursor().execute(
            """INSERT INTO {t} (name, owner, win_rate, turn_win_ave, games)
            VALUES('{dn}', '{do}', 0.0, 0.0, 1)""".format(
                t=deck_table, dn=deck_name, do=deck_owner
            )
        )
        conn.commit()
    finally:
        conn.close()


def merge_into_deck(is_test, deck_name, player_name):
    try:
        conn = connect(is_test)
        c = conn.cursor()
        rows = c.execute("""
        SELECT games FROM {t} WHERE name = '{fn}' and owner = '{pn}'""".format(t=deck_table, fn=deck_name, pn=player_name)).fetchall()
        if len(rows) > 0:
            c.execute("""
            UPDATE {} SET games = {}, win_rate = {} WHERE name = '{}'""".format(deck_table, rows[0][0]+1,
                                                                                calculate_deck_win_rate(is_test, deck_name),
                                                                                deck_name))
            conn.commit()
        else:
            insert_into_deck_table(deck_name, player_name, is_test)
    finally:
        conn.close()


def get_decks_by_player(deck_owner, is_test):
    decks = []
    try:
        conn = connect(is_test)
        c = conn.cursor()
        rows = c.execute(
            """SELECT name
            FROM {t}
            WHERE owner = '{do}'""".format(
                t=deck_table, do=deck_owner
            )
        ).fetchall()
        for row in rows:
            decks.append(row)
        return decks
    finally:
        conn.close()


def insert_into_winner_table(is_test, winners, players, order, style, turns, date, win_con, details, game):
    try:
        query = """INSERT INTO {t} 
            VALUES ('{winners}', '{players}', '{order}', '{style}', {turns}, {date}, '{win}', '{details}', '{game}')
        """.format(
                t=winner_table,
                winners=winners,
                players=players,
                order=order,
                style=style,
                turns=turns,
                date=date,
                win=win_con,
                details=details,
                game=game
            )
        conn = connect(is_test)
        conn.cursor().execute(query)
    finally:
        conn.commit()
        conn.close()


def get_winners(is_test):
    winners = []
    try:
        conn = connect(is_test)
        c = conn.cursor()
        rows = c.execute(
            """
            SELECT winner FROM {}
        """.format(winner_table)).fetchall()
        for row in rows:
            winners.append(row)
        return winners
    finally:
        conn.close()


def get_decks(is_test):
    deck_names = []
    try:
        conn = connect(is_test)
        c = conn.cursor()
        rows = c.execute(
            """
            SELECT name FROM {}
        """.format(deck_table))
        for row in rows:
            deck_names.append(row[0])
        return deck_names
    finally:
        conn.close()


def get_turn_by_winners(is_test):
    try:
        conn = connect(is_test)
        c = conn.cursor()
        c.execute(
            """
            SELECT winner, turns FROM {}
            """.format(winner_table)
        )
    finally:
        conn.close()


def get_games_by_player(is_test, player):
    try:
        conn = connect(is_test)
        c = conn.cursor()
        games = c.execute(
            """
            SELECT games FROM {} WHERE name = '{}'
        """.format(player_table, player)
        ).fetchone()
        return games[0]
    finally:
        conn.close()


def calculate_player_win_rate(is_test, player):
    try:
        conn = connect(is_test)
        c = conn.cursor()
        games = c.execute(
            """
            SELECT games FROM {} WHERE name = '{}'  
            """.format(player_table, player)).fetchone()
        wins = len(get_winners(is_test))

        if wins == 0:
            return 0
        else:
            return games[0]/wins*100
    finally:
        conn.close()


def calculate_deck_win_rate(is_test, deck):
    try:
        conn = connect(is_test)
        c = conn.cursor()
        games = c.execute(
            """
            SELECT games FROM {} WHERE name = '{}'  
            """.format(deck_table, deck)).fetchone()
        wins = len(get_winners(is_test))

        if wins == 0:
            return 0
        else:
            return games[0]/wins*100
    finally:
        conn.close()


def parse_data_by_desc(player, data):
    split_data = data.split(',')
    for info in split_data:
        if info.split(':')[0] == player:
            return info


def parse_data_by_pos(pos, data):
    split_data = data.split(',')
    for info in split_data:
        sp = info.split(':')
        if int(sp[1]) == pos:
            return sp[0]


def insert_into_turns(is_test, game_id, game_round, player_turn, turn_events):
    try:
        query = """INSERT INTO {t} 
               VALUES ('{game}', '{round}', '{active_player}', '{events}')
           """.format(
            t=turns_table,
            game=game_id,
            round=game_round,
            active_player=player_turn,
            events=turn_events
        )
        conn = connect(is_test)
        conn.cursor().execute(query)
    finally:
        conn.commit()
        conn.close()


def insert_into_games(is_test, game_id, player_name, deck_name, position):
    try:
        query = """INSERT INTO {t} 
               VALUES ('{game}', '{player}', '{deck}', '{order}')
           """.format(
            t=games_table,
            game=game_id,
            player=player_name,
            deck=deck_name,
            order=position
        )
        conn = connect(is_test)
        conn.cursor().execute(query)
    finally:
        conn.commit()
        conn.close()


def get_current_game_id(is_test):
    try:
        query = """SELECT MAX(game_id) FROM {t}
           """.format(
            t=games_table
        )
        conn = connect(is_test)
        current_game = conn.cursor().execute(query).fetchone()
    finally:
        conn.commit()
        conn.close()
    return current_game[0]


def get_new_game_id(is_test):
    try:
        query = """SELECT MAX(game_id) FROM {t}
           """.format(
            t=games_table
        )
        conn = connect(is_test)
        current_game = conn.cursor().execute(query).fetchone()
    finally:
        conn.commit()
        conn.close()
    if current_game[0] is None:
        return 0

    return current_game[0] + 1


# get winners done
# get all decks done
# get turn by winners
# calculate player win rate
# calculate deck win rate
# calculate deck turn win rate


# Winner {Mark:1, Brett:3, Chris:3, Greg:4}
# Order {1:Brett, 2:Chris, 3:Greg, 4:Mark}
# Deck {Isshin:1, Shelob:3, Orthion:3, Thoracle:4}
