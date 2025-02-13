from sql.sql import (
    create_player_table,
    insert_into_player,
    get_players,
    create_deck_table,
    insert_into_deck_table,
    get_decks_by_player,
    create_winner_table,
    insert_into_winner_table,
    get_winners,
    get_games_by_player,
    connect,
    winner_table,
    player_table,
    deck_table,
    calculate_player_win_rate,
    merge_into_player
)
import softest
from datetime import date
from sqlite3 import OperationalError


class PlayerTableTest(softest.TestCase):
    def cleanup(self):
        try:
            conn = connect(True)
            conn.execute("""
            DROP TABLE {}""".format(winner_table))
        except OperationalError as e:
            print(e, "Tables have already been dropped")
        finally:
            conn.close()

        try:
            conn = connect(True)
            conn.execute("""
            DROP TABLE {}""".format(player_table))
        except OperationalError as e:
            print(e, "Tables have already been dropped")
        finally:
            conn.close()

        try:
            conn = connect(True)
            conn.execute("""
            DROP TABLE {}""".format(deck_table))
        except OperationalError as e:
            print(e, "Tables have already been dropped")
        finally:
            conn.close()

    def test_insert_and_returning_player(self):
        create_player_table(True)
        name = "Testy McTesterson"
        insert_into_player(name, True)
        players = get_players(True)
        self.assertTrue(players[0], name)
        self.cleanup()

    def test_insert_and_returning_decks(self):
        create_deck_table(True)
        name = "Isshin"
        owner = "Testy McTesterson"
        insert_into_deck_table(name, owner, True)
        decks = get_decks_by_player(owner, True)
        self.assertTrue(decks[0], name)
        self.cleanup()

    def test_insert_and_returning_winners(self):
        create_winner_table(True)
        winners = "Greg:1,Mark:4,Brett:4,Chris:4"
        order = "{Greg: 1, Mark: 4, Brett: 3, Chris: 2}"
        decks = "{Najeela: 1, Exalted: 4, Shelob: 4, Enrage: 4}"

        insert_into_winner_table(True, winners, order, decks, 'Commander', 8, date.today(), 'Greg', 'Infinite Mill')
        db_winners = get_winners(True)
        self.assertEqual(db_winners[0], "Greg")
        self.cleanup()

    def test_format_winners(self):
        p1 = 'Greg'
        p1p = '1'
        p2 = 'Mark'
        p2p = '4'
        p3 = 'Brett'
        p3p = '3'
        p4 = 'Chris'
        p4p = '2'
        assumed_string = 'Greg:1,Mark:4,Brett:3,Chris:2,'
        test_string = format_winners_insert(p1, p1p, p2, p2p, p3, p3p, p4, p4p)
        self.assertEqual(assumed_string, test_string)
        self.cleanup()

    def test_incorrect_format_winners(self):
        p1 = 'Greg'
        p1p = '1'
        p2 = 'Mark'
        p2p = '4'
        p3 = 'Brett'
        p3p = '3'
        p4 = 'Chris'
        try:
            format_winners_insert(p1, p1p, p2, p2p, p3, p3p, p4)
        except Exception as e:
            self.assertTrue(e, ValueError)
            self.assertEqual(e.args[0], 'Please insert equal players and placements')
        finally:
            self.cleanup()

    def test_get_games_by_player(self):
        create_player_table(True)
        insert_into_player('Mark', True)
        games = get_games_by_player(True, 'Mark')
        self.assertEqual(games, 0)
        self.cleanup()

    def test_get_deck_by_player(self):
        create_deck_table(True)
        insert_into_deck_table("Isshin", "Mark", True)
        decks = get_decks_by_player("Mark", True)
        self.assertEqual(decks[0][0], 'Isshin')
        self.cleanup()

    def test_player_win_rate(self):
        create_winner_table(True)
        create_player_table(True)
        merge_into_player('Greg', True)
        winners = "Greg:1,Mark:4,Brett:4,Chris:4"
        order = "{Greg: 1, Mark: 4, Brett: 3, Chris: 2}"
        decks = "{Najeela: 1, Exalted: 4, Shelob: 4, Enrage: 4}"

        insert_into_winner_table(True, winners, order, decks, 'Commander', 8, date.today(), 'Greg', 'Infinite Mill')
        win_rate = calculate_player_win_rate(True, 'Greg')
        self.assertEqual(win_rate, 100)
        self.cleanup()

    def test_merge_player(self):
        create_player_table(True)
        create_winner_table(True)
        merge_into_player('Testy', True)
        merge_into_player('Testy', True)
        merge_into_player('Testy', True)
        games = get_games_by_player(True, 'Testy')
        self.assertEqual(games, 3)
        self.cleanup()
