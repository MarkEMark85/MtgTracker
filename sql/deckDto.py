class DeckDto:
    name = ''
    owner = ''
    win_rate = 0.0
    turn_win_ave = 0.0

    def __init__(self, name, owner, win_rate, turn_win_ave):
        self.name = name
        self.owner = owner
        self.win_rate = win_rate
        self.turn_win_ave = turn_win_ave
