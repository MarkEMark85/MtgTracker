from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox


class StatsScreen(Screen):
    def __init__(self, **kwargs):
        super(StatsScreen, self).__init__(**kwargs)

        self.grid = GridLayout(cols=1)
        self.stats = GridLayout(cols=1)
        self.input = GridLayout(cols=2, size_hint_y=None, height=200)
        # stats grid
        self.wins = Label(text='Brett won 4/21 - 19.05%')
        self.pod = Label(text='''Brett won 1/5 - 20.00% pod:Brett Chris Mark
Brett won 1/5 - 20.00% pod:Brett Chris Coltrin Greg Mark
Brett won 1/3 - 33.33% pod:Brett Chris Coltrin Mark
Brett won 1/5 - 20.00% pod:Brett Chris Coltrin''', color='grey')
        self.match_up = Label(text="Brett {'Chris': '4/5', 'Mark': '3/4', 'Coltrin': '3/3', 'Greg': '1/2'}")
        self.stats.add_widget(self.wins)
        self.stats.add_widget(self.pod)
        self.stats.add_widget(self.match_up)

        # input grid
        self.description = Label(text='search players')
        self.change = CheckBox()
        self.player = TextInput()
        self.submit = Button(text='Get Stats', background_color='blue')
        self.input.add_widget(self.description)
        self.input.add_widget(self.change)
        self.input.add_widget(self.player)
        self.input.add_widget(self.submit)

        self.add_widget(self.grid)
        self.grid.add_widget(self.stats)
        self.grid.add_widget(self.input)
