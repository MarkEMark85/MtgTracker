from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from gameScreen import GameScreen


class InitScreen(Screen):

    def __init__(self, **kwargs):
        super(InitScreen, self).__init__(**kwargs)
        self.grid = GridLayout(cols=1)
        self.inside_grid = GridLayout(cols=2)

        self.inside_grid.add_widget(Label(text='Number Of Players'))
        self.inside_grid.players = TextInput(text='4', multiline=False, halign='center')
        self.inside_grid.players.font_size = str(self.inside_grid.players.height+50)
        self.inside_grid.add_widget(self.inside_grid.players)

        self.grid.next_button = Button(text='Next', background_color='blue', on_press=self.go_to_game)
        self.grid.add_widget(self.inside_grid)
        self.grid.add_widget(self.grid.next_button)

        self.grid.menu_button = Button(text='Menu', on_press=self.go_to_menu)
        self.grid.add_widget(self.grid.menu_button)
        self.add_widget(self.grid)

    def go_to_game(self, instance):
        self.parent.add_widget(GameScreen(name='Game', players=int(self.inside_grid.players.text)))
        self.parent.current = 'Game'

    def go_to_menu(self, instance):
        self.parent.current = 'Menu'



