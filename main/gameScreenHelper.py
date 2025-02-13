from kivy.uix.textinput import TextInput


def create_form():
    p_name = TextInput(background_color='gray', multiline='false', size_hint_x=None, width=300)
    p_deck = TextInput()
    p_pos = TextInput(size_hint_x=None, width=100)
    p_end = TextInput(size_hint_x=None, width=100)
    return p_name, p_deck, p_pos, p_end


def collect_children_text(children):
    texts = []
    for child in children:
        texts.append(child.text)
    return texts
