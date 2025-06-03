from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from endGameScreen import EndGameScreen
from sql.sql import insert_into_turns


class TurnsScreen(Screen):

    def __init__(self, players, is_test, game_id, **kwargs):
        super(TurnsScreen, self).__init__(**kwargs)
        self.is_test = is_test
        self.game_id = game_id
        self.players = players
        self.main_grid = GridLayout(cols=1)
        self.turn_grid = GridLayout(cols=len(players)*2)
        self.damage_grid = GridLayout(cols=len(players) + 2)
        self.counter_grid = GridLayout(cols=3, size_hint_y=None, height=250)

        self.counter_grid.counter = 1

        self.lower_button = Button(text='<', on_press=self.sub_one, background_color='black')
        self.counter_grid.add_widget(self.lower_button)

        self.counter_grid.count_label = Label(text=str(self.counter_grid.counter), color='orange', font_size=250)
        self.counter_grid.add_widget(self.counter_grid.count_label)

        self.raise_button = Button(text='>', on_press=self.add_one, background_color='black')
        self.counter_grid.add_widget(self.raise_button)

        self.next_button = Button(text='Next Turn', on_press=self.new_turn)
        self.end_button = Button(text='End Game', on_press=self.go_to_end_screen)

        self.create_turn_checks()
        self.create_damage_grid()
        self.main_grid.add_widget(self.turn_grid)
        self.main_grid.add_widget(self.counter_grid)
        self.main_grid.add_widget(self.damage_grid)
        self.main_grid.add_widget(self.next_button)
        self.main_grid.add_widget(self.end_button)
        self.add_widget(self.main_grid)

    def sub_one(self, instance):
        self.counter_grid.counter -= 1
        self.counter_grid.count_label.text = str(self.counter_grid.counter)

    def add_one(self, instance):
        self.counter_grid.counter += 1
        self.counter_grid.count_label.text = str(self.counter_grid.counter)

    def create_turn_checks(self):
        counter = 0
        for player in self.players:
            self.turn_grid.add_widget(Label(text=player, text_size=(80, 0), halign='right'))
            if counter == 0:
                self.turn_grid.add_widget(CheckBox(group='players', active=True))
                counter += 1
            else:
                self.turn_grid.add_widget(CheckBox(group='players'))

    def create_damage_grid(self):
        count = 0
        for player in self.players:
            if count == 0:
                self.damage_grid.add_widget(Label(text=''))
            self.damage_grid.add_widget(Label(text=player))
            if count == len(self.players)-1:
                self.damage_grid.add_widget(Label(text='Life Totals'))
            count += 1
        for player in self.players:
            self.damage_grid.add_widget(Label(text=player, text_size=(80, 0), halign='left'))

            for i in range(len(self.players) + 1):
                if i % len(self.players) != 0 or i == 0:
                    self.damage_grid.add_widget(TextInput(multiline=False))
                else:
                    self.damage_grid.add_widget(TextInput(text='40', multiline=False, halign='center'))

    def new_turn(self, instance):
        fields = self.collect_children_text(self.damage_grid.children)
        rows = []
        column_count = len(self.players)+2
        count = 0
        this_row = []
        for field in fields:
            if count < column_count:
                this_row.append(field)
                count += 1
                if count == column_count:
                    rows.append(this_row)
                    this_row = []
                    count = 0
        self.do_the_math(rows)
        insert_into_turns(self.is_test, self.game_id, self.counter_grid.children[1],
                          self.get_active_player(), self.rows_to_text(rows))
        self.update_children(self.damage_grid.children, rows)

    def go_to_end_screen(self, instance):
        self.parent.switch_to(EndGameScreen(name='End', players=self.players, turns=self.counter_grid.counter,
                                            is_test=self.is_test, game_id=self.game_id))

    def get_active_player(self):
        children = self.turn_grid.children
        counter = 0
        for child in children:
            if type(child) == CheckBox:
                if child.active:
                    return children[counter+1]
            counter += 1

    def rows_to_text(self, rows):
        temp_rows = []
        temp_rows.extend(rows)
        temp_rows.pop(0)
        ret_val = ''
        for row in temp_rows:
            ret_val += row[0] + ' ' + row[len(self.players)+1]

    @staticmethod
    def do_the_math(temporary_health):
        for i in range(1, len(temporary_health)):
            sumt = 0
            life = int(temporary_health[i][len(temporary_health)])
            for j in range(1, len(temporary_health)):
                added_life = temporary_health[j][i]
                if added_life == '':
                    added_life = '0'
                sumt += int(added_life)
                temporary_health[j][i] = ''
            temporary_health[i][len(temporary_health)] = str(life - sumt)

    @staticmethod
    def collect_children_text(children):
        texts = []
        children.reverse()
        for child in children:
            texts.append(child.text)
        return texts

    @staticmethod
    def update_children(children, updated_list):
        wrap_count = len(updated_list[1])
        i_count = 0
        j_count = 0
        for child in children:
            child.text = updated_list[i_count][j_count]
            j_count += 1
            if j_count == wrap_count:
                j_count = 0
                i_count += 1
        children.reverse()

