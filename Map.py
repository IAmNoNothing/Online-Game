from loguru import logger
import pygame as pg


class Map:
    def __init__(self, map_proto):
        color_map = self.create_color_map(map_proto.color_map)
        map_array = map_proto.map
        width = max(map(len, map_array))
        height = len(map_array)

        pixels_per_block = min(800 // width, 600 // height)
        surface = pg.Surface((pixels_per_block * width, pixels_per_block * height))

        for y in range(height):
            for x in range(width):
                current_value = map_array[y][x]

                color = (255, 255, 255)
                if current_value == ' ':
                    continue

                if current_value not in color_map:
                    logger.error(f"Unknown color entry: `{current_value}`")
                    continue

                color = color_map[current_value]

                pg.draw.rect(
                    surface, color,
                    (pixels_per_block * x, pixels_per_block * y, pixels_per_block, pixels_per_block)
                )
        
        self.surface = surface
        self.pixels_per_block = pixels_per_block
        self.width = width
        self.height = height
        self.color_map = color_map
        self.rect = self.surface.get_rect(center=(400, 300))

    def create_color_map(self, raw_color_map):
        color_map = {entry.identifier: (entry.color.r, entry.color.g, entry.color.b) for entry in raw_color_map}
        return color_map