from datetime import date


class WinnerDto:
    winner = ''
    deck = ''
    turn_order = ''
    style = 'Commander'
    turns = ''
    date = date.today()
    win_con = ''
    win_details = ''

    def __init__(self, winner, deck, turn_order, turns, win_con, win_details):
        self.winner = winner
        self.deck = deck
        self.turn_order = turn_order
        self.turns = turns
        self.win_con = win_con
        self.win_details = win_details
