from kivy.app import App
from initScreen import InitScreen
from menuScreen import MenuScreen
from statScreen import StatsScreen
from kivy.uix.screenmanager import ScreenManager


class Main(App):
    manager = ScreenManager()
    manager.add_widget(MenuScreen(name='Menu'))
    manager.add_widget(InitScreen(name='Init'))
    manager.add_widget(StatsScreen(name='Stats'))

    def build(self):
        self.icon = 'mtg_stats.ico'
        self.title = 'Magic Stats'
        return self.manager


if __name__ == '__main__':
    Main().run()
