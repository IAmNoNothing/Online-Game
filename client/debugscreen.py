import pygame as pg


class Box:
    def __init__(self, value):
        self.value = value
    

class DebugScreen:
    def __init__(self, screen):
        self.values = {}
        self.font = pg.font.Font('assets/Tiny5-Regular.ttf', 20)
        self.screen = screen

    def set_value(self, name, value):
        if name not in self.values:
            self.values[name] = Box(value)
        else:
            self.values[name].value = value
    
    def draw(self):
        for i, (name, box) in enumerate(self.values.items()):
            text = self.font.render(f"{name}: {box.value}", False, (255, 255, 255))
            self.screen.blit(text, (10, 10 + i * (self.font.get_height() + 5)))
