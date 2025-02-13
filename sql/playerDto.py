# from sql import get_

class PlayerDto:
    name = ''
    win_rate = 0.0
    games = 0

    def __init__(self, name, games=0, win_rate=0.0):
        self.name = name
        self.win_rate = win_rate
        self.games = games


