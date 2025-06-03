from kivy.app import App
from initScreen import InitScreen
from menuScreen import MenuScreen
from statScreen import StatsScreen
from kivy.uix.screenmanager import ScreenManager
from sql.sql import create_all_tables


class Main(App):
    is_test = True
    manager = ScreenManager()
    manager.add_widget(MenuScreen(name='Menu', is_test=is_test))
    manager.add_widget(InitScreen(name='Init', is_test=is_test))
    # manager.add_widget(StatsScreen(name='Stats', is_test=is_test))

    def build(self):
        create_all_tables(self.is_test)
        self.icon = 'mtg_stats.ico'
        self.title = 'Magic Stats'
        return self.manager


if __name__ == '__main__':
    Main().run()
