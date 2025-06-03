from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from datetime import date
from sql.sql import insert_into_winner_table


class EndGameScreen(Screen):

    def __init__(self, players, turns, is_test, game_id, **kwargs):
        super(EndGameScreen, self).__init__(**kwargs)
        self.game_id = game_id
        self.players = players
        self.turns = turns
        self.is_test = is_test
        self.main_grid = GridLayout(cols=1)
        self.name_info = GridLayout(cols=len(players)+1)
        self.name_info.add_widget(Label(text='Name:', halign='left', text_size=(200, 0), font_size='30'))
        self.deck_info = GridLayout(cols=len(players)+1)
        self.deck_info.add_widget(Label(text='Deck:', halign='left', text_size=(200, 0), font_size='30'))
        self.pos_info = GridLayout(cols=len(players)+1)
        self.pos_info.add_widget(Label(text='Turn Order:', halign='left', text_size=(200, 0), font_size='30'))
        self.win_info = GridLayout(cols=len(players)+1, height='80', size_hint_y=None)
        self.win_info.add_widget(Label(text='Win Order:', halign='left', text_size=(200, 0), font_size=str(self.win_info.height-50)))
        self.other_info = GridLayout(cols=2)
        self.other_info.add_widget(Label(text='Turns:', halign='left', text_size=(200, 0), font_size=str(self.win_info.height-50)))
        self.other_info.add_widget(TextInput(text=str(turns), halign='center', font_size=str(self.other_info.height-30)))
        self.other_info.add_widget(TextInput(text='Win_con', halign='center', font_size=str(self.other_info.height-30)))
        self.other_info.add_widget(TextInput(text='Win_details', halign='center', font_size=str(self.other_info.height-30)))
        
        self.get_game_info()
        self.insert_win_tabs()
        self.main_grid.add_widget(Button(text='Save', font_size='40', background_color='blue', on_release=self.save_game))
        self.main_grid.add_widget(self.name_info)
        self.main_grid.add_widget(self.deck_info)
        self.main_grid.add_widget(self.pos_info)
        self.main_grid.add_widget(self.win_info)
        self.main_grid.add_widget(self.other_info)
        self.add_widget(self.main_grid)

    def get_game_info(self):
        with open('game_info.csv', 'r') as reader:
            reader.readline()
            count = 0
            for line in reader:
                split = line.split(',')
                for item in split:
                    if count == 0:
                        self.name_info.add_widget(Label(text=item, font_size='30'))
                        count += 1
                    elif count == 1:
                        self.deck_info.add_widget(Label(text=item, font_size='30'))
                        count += 1
                    else:
                        self.pos_info.add_widget(Label(text=item, font_size='30'))
                        count = 0

    def insert_win_tabs(self):
        for _ in range(len(self.players)):
            self.win_info.add_widget(TextInput(halign='center', font_size=str(self.win_info.height-20)))

    def save_game(self, instance):
        winner_info = self.get_winner_info()
        insert_into_winner_table(self.is_test, self.name_info.children[winner_info].text.strip(),
                                 self.deck_info.children[winner_info].text.strip(),
                                 self.pos_info.children[winner_info].text.strip(),
                                 'Commander', self.other_info.children[2].text.strip(), date.today(),
                                 self.other_info.children[1].text.strip(), self.other_info.children[0].text.strip(),
                                 self.game_id)
        self.parent.current = 'Menu'

    def get_winner_info(self):
        children = self.win_info.children
        counter = 0
        for child in children:
            if child.text == '1':
                return counter
            counter += 1
