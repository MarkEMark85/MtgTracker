from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen


class MenuScreen(Screen):

    def __init__(self, **kwargs):
        super(MenuScreen, self).__init__(**kwargs)
        self.grid = GridLayout()
        self.grid.cols = 1
        self.grid.add_widget(Label(text='Magic'))
        self.grid.add_widget(Label(text='Stats'))
        self.grid.add_widget(Button(text='Check Stats', on_press=self.go_to_stats))
        self.grid.add_widget(Button(text='Enter Stats', on_press=self.go_to_init))
        self.add_widget(self.grid)

    def go_to_init(self, instance):
        self.parent.current = 'Init'

    def go_to_stats(self, instance):
        self.parent.current = 'Stats'
