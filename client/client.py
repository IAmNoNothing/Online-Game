import grpc
import game_pb2
import game_pb2_grpc
import pygame as pg
import threading
import time
from loguru import logger
import math
from client.debugscreen import DebugScreen
from Map import Map


def lerp(a, b, t):
    return a + (b - a) * t


def step(n, s):
    return round(n / s) * s


def clamp(value, min_value, max_value):
    return max(min(value, max_value), min_value)


class Player:
    radius = 10
    def __init__(self, position, direction, name):
        self.position = position
        self.direction = direction
        self.last_position = position
        self.last_direction = direction
        self.speed = 200
        self.name = name
        self.last_update = time.time()
        self.last_last_update = time.time()
        self.name_surface = GameClient.instance.font.render(self.name, False, (255, 255, 255))
        self.interpolation = 0
        self.interpolate = False
        self.interpolated_position = self.position.copy()
        
        self.hp = 100
        self.main_player = False
        big_font = pg.font.Font('assets/Tiny5-Regular.ttf', 40)
        self.gameover = big_font.render("You are dead!", False, (255, 100, 100))

    def update_pos_and_dir(self, position, direction):
        self.last_position = self.position.copy()
        self.last_direction = self.direction
        self.position = position.copy()
        self.direction = direction
        self.last_last_update = self.last_update
        self.last_update = time.time()

    def move(self, dt):
        if self.dead():
            return
        
        keys = pg.key.get_pressed()
        movement = pg.Vector2(0, 0)

        if keys[pg.K_w]:
            movement.y -= 1
        elif keys[pg.K_s]:
            movement.y += 1
        
        if keys[pg.K_a]:
            movement.x -= 1
        elif keys[pg.K_d]:
            movement.x += 1

        if movement.length_squared() > 0:
            movement = movement.normalize()

        position = self.position.copy()
        position.x += movement.x * self.speed * dt
        position.y += movement.y * self.speed * dt

        position.x = clamp(position.x, self.radius, GameClient.instance.w - self.radius)
        position.y = clamp(position.y, self.radius, GameClient.instance.h - self.radius)

        collides, where = self.collides_with_map(position)
        if not collides:
            self.position = position
        
        # match where:
        #     case 'up':
        #         self.position.x = position.x
        #         self.position.y = position.y + 1
        #     case 'down':
        #         self.position.x = position.x
        #         self.position.y = position.y - 1
        #     case 'left':
        #         self.position.y = position.y
        #         self.position.x = position.x + 1
        #     case 'right':
        #         self.position.y = position.y
        #         self.position.x = position.x - 1
            

    def collides_with_map(self, position: pg.Vector2):
        if GameClient.instance.text_map is None or GameClient.instance.map is None:
            return True, -1
        
        ppb = GameClient.instance.map.pixels_per_block
        collision_box = pg.Rect(position.x - self.radius, position.y - self.radius, self.radius * 2, self.radius * 2)
        map_top_left = GameClient.instance.map.rect.topleft

        for y, row in enumerate(GameClient.instance.text_map):
            for x, cell in enumerate(row):
                if cell == ' ':
                    continue

                cell_rect = pg.Rect(x * ppb + map_top_left[0], y * ppb + map_top_left[1], ppb, ppb)
                if collision_box.colliderect(cell_rect):
                    return True, self.collision_direction(cell_rect, collision_box)
        
        return False, -1
    
    def collision_direction(self, a, b):
        a_center_x = a.x + a.w / 2
        a_center_y = a.y + a.h / 2
        b_center_x = b.x + b.w / 2
        b_center_y = b.y + b.h / 2

        dx = b_center_x - a_center_x
        dy = b_center_y - a_center_y

        half_widths = (a.w + b.w) / 2
        half_heights = (a.h + b.h) / 2

        overlap_x = half_widths - abs(dx)
        overlap_y = half_heights - abs(dy)

        if overlap_x < overlap_y:
            if dx > 0:
                return "left" 
            else:
                return "right"
        else:
            if dy > 0:
                return "up" 
            else:
                return "down"

    def update_direction(self):
        mx, my = pg.mouse.get_pos()
        dx = mx - self.position.x
        dy = my - self.position.y

        if dx == 0 and dy == 0:
            return
        
        self.direction = math.atan2(dy, dx)

    def update(self, dt):
        self.move(dt)
        self.update_direction()
        self.interpolation = (time.time() - self.last_last_update) / (self.last_update - self.last_last_update)
    
    def dead(self):
        return self.hp <= 0

    def draw(self, screen):
        if not self.dead():
            self.draw_circle(screen)
            self.draw_sight_line(screen)
            self.draw_name(screen)
        elif self.main_player:
            screen.blit(self.gameover, self.gameover.get_rect(center=(400, 300)))          

    def draw_sight_line(self, screen):
        if not self.interpolate:
            offset = pg.Vector2(math.cos(self.direction) * 20, math.sin(self.direction) * 20)
            pg.draw.line(screen, (0, 255, 0), self.position, self.position + offset, 2)
            return

        direction = self.last_direction + self.interpolation * (self.direction - self.last_direction)
        offset = pg.Vector2(math.cos(direction) * 20, math.sin(direction) * 20)
        dp = self.position - self.last_position
        position = self.last_position.copy()
        position.x += dp.x * self.interpolation
        position.y += dp.y * self.interpolation
        
        pg.draw.line(screen, (0, 255, 0), position, position + offset, 2)

    def draw_name(self, screen):
        if not self.interpolate:
            screen.blit(self.name_surface, (self.position.x - self.name_surface.get_width() // 2, self.position.y - 30))
            return
        dp = self.position - self.last_position
        position = self.last_position.copy()
        position.x += dp.x * self.interpolation
        position.y += dp.y * self.interpolation
        screen.blit(self.name_surface, (position.x - self.name_surface.get_width() // 2, position.y - 30))

    def draw_circle(self, screen):
        if not self.interpolate:
            pg.draw.circle(screen, (0, 0, 255), self.position, self.radius)
            return
        dp = self.position - self.last_position
        position = self.last_position.copy()
        position.x += dp.x * self.interpolation
        position.y += dp.y * self.interpolation
        pg.draw.circle(screen, (255, 0, 0), position, self.radius)

class Bullets:
    def __init__(self):
        self.bullets = []
        self.bullet_sprites = {}
        self.raw_bullet_sprite = pg.transform.scale_by(pg.image.load("assets/bullet.png").convert_alpha(), 2)
        self.angle_count = 36
    
    def add(self, bullet):
        self.bullets.append(bullet)
    
    def clear(self):
        self.bullets.clear()
    
    def get_bullet_sprite(self, rot):
        rot = step(rot, 2 * math.pi / self.angle_count)
        if rot not in self.bullet_sprites:
            bullet_sprite = pg.transform.rotate(self.raw_bullet_sprite, rot * 180 / math.pi - 90)
            self.bullet_sprites[rot] = bullet_sprite
        return self.bullet_sprites[rot]

    def draw(self, screen):
        for bullet in self.bullets:
            angle = math.atan2(-bullet.direction.y, bullet.direction.x)
            sprite = self.get_bullet_sprite(angle)
            screen.blit(sprite, sprite.get_rect(center=(bullet.position.x, bullet.position.y)))

class GameClient:
    instance = None
    def __init__(self, name):
        GameClient.instance = self
        self.network_thread = None
        self.running = False
        self.w, self.h = 800, 600
        self.dt = 0
        pg.init()
        self.screen = pg.display.set_mode((self.w, self.h))
        pg.display.set_caption("Game Client")
        self.clock = pg.time.Clock()
        self.client_id = name
        self.font = pg.font.Font('assets/Tiny5-Regular.ttf', 14)

        self.player = Player(pg.Vector2(0, 0), 0, self.client_id)
        self.player.position = pg.Vector2(self.w // 2, self.h // 2)
        self.player.interpolate = False
        self.player.main_player = True

        self.debug_screen = DebugScreen(self.screen)
        self.debug_screen.set_value("FPS", 0)
        self.players = {}
        logger.info(f"Game client initialized. Whale cum, {self.client_id}!")
        self.bullets = Bullets()
        self.must_shoot = False
        self.map = None
        self.text_map = None

    def run(self):
        self.running = True
        self.network_thread = threading.Thread(target=self.network_loop)
        self.network_thread.start()

        logger.info("Network thread started.")
        logger.info("Starting main loop...")
        self.main_loop()
        logger.info("Main loop finished")
        logger.info("Waiting for network thread to finish...")

        self.network_thread.join()
        logger.info("Network thread finished")
        logger.info("Exiting...")
        pg.quit()
    
    def connect(self):
        channel = grpc.insecure_channel('localhost:12345')
        try:
            stub = game_pb2_grpc.GameStub(channel)
            request = game_pb2.JoinRequest(player_id=self.client_id)
            response = stub.Join(request)
        except grpc._channel._InactiveRpcError as e:
            logger.error("Failed to connect to server. Is it running?")
            logger.error(f"Error:\n{e}")
            self.quit_main_loop()
            return

        if not response.success:
            logger.error("Failed to join the game.")
            self.quit_main_loop()
            return
        else:
            logger.success("Joined the game successfully!")
        
        self.text_map = response.map.map
        self.map = Map(response.map)
        logger.info("Created map surface.")

        return channel, stub

    def network_loop(self):
        channel_stub = self.connect()
        if channel_stub is None:
            return
        channel, stub = channel_stub

        while self.running:
            time.sleep(1 / 60)
            position = game_pb2.Vec2(x=self.player.position.x, y=self.player.position.y)
            request = game_pb2.UpdateRequest(client_id=self.client_id, position=position, direction=self.player.direction)
            response = stub.Update(request)
            player_states = response.states
            self.bullets.bullets = response.bullets
            self.process_player_states(player_states)

            if self.must_shoot:
                shoot_request = game_pb2.ShootRequest(player_id=self.client_id)
                stub.Shoot(shoot_request)
                self.must_shoot = False
        
        request = game_pb2.LeaveRequest(player_id=self.client_id)
        response = stub.Leave(request)
        logger.info("Left the game.")  
        logger.info("Closing connection...")
        channel.close()
    
    def process_player_states(self, player_states):
        current_ids = set(self.players.keys())
        incoming_ids = set(state.client_id for state in player_states if state.client_id != self.client_id)

        for removed_id in current_ids - incoming_ids:
            del self.players[removed_id]

        for state in player_states:
            if state.client_id == self.client_id:
                self.player.hp = state.hp
                continue
             
            if state.client_id not in self.players:
                self.players[state.client_id] = Player(pg.Vector2(state.position.x, state.position.y), state.direction, state.client_id)
            else:
                player = self.players[state.client_id]
                player.update_pos_and_dir(pg.Vector2(state.position.x, state.position.y), state.direction)
                player.hp = state.hp

    def draw_players(self):
        for player in self.players.values():
            player.draw(self.screen)
        self.player.draw(self.screen)

    def main_loop(self):
        while self.running:
            self.events()
            self.update()
            self.render()

    def events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                logger.info("Quitting...")
                self.quit_main_loop()
            if event.type == pg.MOUSEBUTTONDOWN:
                if event.button == 1 and not self.player.dead():
                    self.must_shoot = True

    def update(self):
        self.dt = self.clock.tick() / 1000
        self.player.update(self.dt)

        try:
            self.debug_screen.set_value("FPS", int(self.clock.get_fps()))
        except OverflowError:
            self.debug_screen.set_value("FPS", "NaN")

        # self.debug_screen.set_value("Position", f"({self.player.position.x:.2f}, {self.player.position.y:.2f})")
        # self.debug_screen.set_value("Direction", f"{math.degrees(self.player.direction):.2f}°")
        self.debug_screen.set_value("HP", self.player.hp)
    
    def render(self):
        self.screen.fill((0, 0, 0))
        if self.map is not None:
            self.screen.blit(self.map.surface, self.map.surface.get_rect(center=(self.w / 2, self.h / 2)))
        self.draw_players()
        self.debug_screen.draw()
        self.bullets.draw(self.screen)
        pg.display.flip()

    def quit_main_loop(self):
        self.running = False
        