from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from statScreen import StatsScreen


class MenuScreen(Screen):

    def __init__(self, is_test, **kwargs):
        super(MenuScreen, self).__init__(**kwargs)
        self.is_test = is_test
        self.grid = GridLayout()
        self.grid.cols = 1
        self.grid.add_widget(Label(text='Magic'))
        self.grid.add_widget(Label(text='Stats'))
        self.grid.add_widget(Button(text='Check Stats', on_release=self.go_to_stats))
        self.grid.add_widget(Button(text='Enter Stats', on_release=self.go_to_init))
        self.add_widget(self.grid)

    def go_to_init(self, instance):
        self.parent.current = 'Init'


    def go_to_stats(self, instance):
        self.parent.add_widget(StatsScreen(name='Stats', is_test=self.is_test))
        self.parent.current = 'Stats'
