from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from turnsScreen import TurnsScreen
from sql.sql import get_new_game_id, insert_into_games, merge_into_player, merge_into_deck, get_players


class GameScreen(Screen):
    def __init__(self, players, is_test, **kwargs):
        super(GameScreen, self).__init__(**kwargs)
        self.main_grid = GridLayout(cols=1)
        self.player_grid = GridLayout(cols=3, spacing=[5, 10])
        self.is_test = is_test

        # Adding Player Header
        self.player_grid.add_widget(Label(text='Player', size_hint_x=None, width=300, size_hint_y=None, height=150))
        self.player_grid.add_widget(Label(text='Deck', size_hint_y=None, height=150))
        self.player_grid.add_widget(Label(text='Pos', size_hint_x=None, width=100, size_hint_y=None, height=150))

        for _ in range(0, players):
            data = self.create_form(
                
            )
            self.player_grid.add_widget(data[0])
            self.player_grid.add_widget(data[1])
            self.player_grid.add_widget(data[2])

        self.save_button = Button(text='Next', size_hint_y=None, height=150, background_color='blue',
                                  on_release=self.go_next)

        self.main_grid.add_widget(self.save_button)
        self.main_grid.add_widget(self.player_grid)
        self.add_widget(self.main_grid)

    def go_next(self, instance):
        texts = self.collect_children_text(self.player_grid.children)
        texts.reverse()
        count = 0
        players = []
        game_id = get_new_game_id(self.is_test)
        for _ in range(int(len(texts) / 3)):
            line = ''
            for _ in range(3):
                line += '{}, '.format(texts[count].capitalize())
                count += 1
            if count == 3:
                with open('game_info.csv', 'w') as writer:
                    writer.write(line.removesuffix(', '))
                    writer.write('\n')
            else:
                if count % 3 == 0:
                    line_data = line.split(',')
                    player = line_data[0].strip().capitalize()
                    deck = line_data[1].strip().capitalize()
                    order = line_data[2].strip()
                    merge_into_player(self.is_test, player)
                    merge_into_deck(self.is_test, deck, player)
                    insert_into_games(self.is_test, game_id, player, deck, order)
                    players.append(texts[count - 3].capitalize())
                with open('game_info.csv', 'a') as writer:
                    writer.write(line.removesuffix(', '))
                    writer.write('\n')
        self.parent.switch_to(TurnsScreen(name='Turns', players=players, is_test=self.is_test, game_id=game_id))

    def create_form(self):
        p_name = TextInput(background_color='gray', multiline='false', size_hint_x=None, width=300, hint_text=self.players_to_string())
        p_deck = TextInput()
        p_pos = TextInput(size_hint_x=None, width=100)
        return p_name, p_deck, p_pos

    @staticmethod
    def collect_children_text(children):
        texts = []
        for child in children:
            texts.append(child.text)
        return texts

    def players_to_string(self):
        players = get_players(self.is_test)
        ret_val = ''
        for player in players:
            ret_val += player + ', '
        return ret_val

