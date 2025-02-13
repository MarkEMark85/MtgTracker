from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from turnsScreen import TurnsScreen


class GameScreen(Screen):
    def __init__(self, players, **kwargs):
        super(GameScreen, self).__init__(**kwargs)
        self.main_grid = GridLayout(cols=1)
        self.win_grid = GridLayout(cols=3, size_hint_y=None, height=150)
        self.player_grid = GridLayout(cols=3, spacing=[5, 10])

        self.win_grid.add_widget(Label(text='Win Con'))
        self.win_grid.win_con = TextInput()
        self.win_grid.add_widget(self.win_grid.win_con)
        self.win_grid.detail = TextInput()
        self.win_grid.add_widget(self.win_grid.detail)
        # Adding Player Header
        self.player_grid.add_widget(Label(text='Player', size_hint_x=None, width=300, size_hint_y=None, height=150))
        self.player_grid.add_widget(Label(text='Deck', size_hint_y=None, height=150))
        self.player_grid.add_widget(Label(text='Pos', size_hint_x=None, width=100, size_hint_y=None, height=150))

        for _ in range(0, players):
            data = self.create_form()
            self.player_grid.add_widget(data[0])
            self.player_grid.add_widget(data[1])
            self.player_grid.add_widget(data[2])


        self.save_button = Button(text='Next', size_hint_y=None, height=150, background_color='blue', on_press=self.go_next)

        self.main_grid.add_widget(self.save_button)
        self.main_grid.add_widget(self.player_grid)
        self.add_widget(self.main_grid)

    def go_next(self, instance):
        texts = self.collect_children_text(self.player_grid.children)
        texts.reverse()
        count = 0
        players = []
        for _ in range(int(len(texts)/3)):
            line = ''
            for _ in range(3):
                line += '{}, '.format(texts[count])
                count += 1
            if count == 3:
                with open('game_info.csv', 'w') as writer:
                    writer.write(line.removesuffix(', '))
                    writer.write('\n')
            else:
                if count % 3 == 0:
                    players.append(texts[count-3])
                with open('game_info.csv', 'a') as writer:
                    writer.write(line.removesuffix(', '))
                    writer.write('\n')
        self.parent.add_widget(TurnsScreen(name='Turns', players=players))
        self.parent.current = 'Turns'



    @staticmethod
    def create_form():
        p_name = TextInput(background_color='gray', multiline='false', size_hint_x=None, width=300)
        p_deck = TextInput()
        p_pos = TextInput(size_hint_x=None, width=100)
        return p_name, p_deck, p_pos

    @staticmethod
    def collect_children_text(children):
        texts = []
        for child in children:
            texts.append(child.text)
        return texts
