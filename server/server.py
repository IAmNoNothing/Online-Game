import grpc
import game_pb2
import game_pb2_grpc
from concurrent import futures
from loguru import logger
import threading
import time
import math
import json
from Map import Map
import pygame as pg


RUNNING = True


class GameServicer(game_pb2_grpc.GameServicer):
    def __init__(self):
        self.players = {}
        self.hps = {}
        self.bullets = []
        self.update_thread = threading.Thread(target=self.update_loop)
        self.update_thread.start()
        self.bullet_id_counter = 0
        self.map_proto = self.create_map_proto_object()
        self.text_map = self.map_proto.map
        self.map = Map(self.map_proto)

    def Join(self, request, context):
        logger.info(f"Player {request.player_id} joined the game.")
        if request.player_id in self.players:
            return game_pb2.JoinResponse(message="Player ID already exists!", success=False)
        self.add_player(request)
        return game_pb2.JoinResponse(message="Successfully joined the game!", success=True, map=self.map_proto)

    def add_player(self, request):
        player_state = game_pb2.PlayerState(
            client_id=request.player_id, 
            position=game_pb2.Vec2(x=0, y=0), 
            direction=0.0
        )
        self.players[request.player_id] = player_state
        self.hps[request.player_id] = 100
        logger.info(f"Added player {request.player_id} to the game.")

    def Leave(self, request, context):
        logger.info(f"Player {request.player_id} left the game.")
        if request.player_id not in self.players:
            return game_pb2.LeaveResponse(message="Player ID does not exist!", success=False)
        del self.players[request.player_id]
        return game_pb2.LeaveResponse(message="Successfully left the game!", success=True)

    def Update(self, request, context):
        self.update_player(request)
        response = game_pb2.UpdateResponse(states=self.players.values(), bullets=self.bullets)
        return response

    def update_player(self, request):
        if request.client_id not in self.players:
            return
        player_state = self.players[request.client_id]
        player_state.position.x = request.position.x
        player_state.position.y = request.position.y
        player_state.direction = request.direction
        player_state.hp = self.hps[request.client_id]
    
    def update_loop(self):
        global RUNNING
        logger.info("Update thread started!")
        last_time = time.time()
        dt = 0
        while RUNNING:
            time.sleep(1 / 60)
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            self.update_bullets(dt)

    def update_bullets(self, dt):
        bullet_speed = 500
        for bullet in self.bullets:
            bullet.position.x += bullet.direction.x * bullet_speed * dt
            bullet.position.y += bullet.direction.y * bullet_speed * dt
            if not self.in_bounds(bullet.position) or self.inside_wall(bullet.position):
                self.bullets.remove(bullet)
            collides, who = self.collides_with_players(bullet)
            if collides:
                self.hps[who.client_id] -= 10
                self.bullets.remove(bullet)

    def collides_with_players(self, bullet):
        for player in self.players.values():
            if player.client_id == bullet.owner_id:
                continue
            if self.hps[player.client_id] <= 0:
                continue
            player_collider = pg.Rect(
                player.position.x - 10, 
                player.position.y - 10, 
                20,
                20
            )
            if player_collider.collidepoint(bullet.position.x, bullet.position.y):
                return True, player
        return False, None

    
    def inside_wall(self, position):        
        ppb = self.map.pixels_per_block
        map_top_left = self.map.rect.topleft

        for y, row in enumerate(self.text_map):
            for x, cell in enumerate(row):
                if cell == ' ':
                    continue

                cell_rect = pg.Rect(x * ppb + map_top_left[0], y * ppb + map_top_left[1], ppb, ppb)
                if cell_rect.collidepoint(position.x, position.y):
                    return True
        
        return False


    def in_bounds(self, position): # too bad, will break if client's map size changes
        return 0 <= position.x <= 800 and 0 <= position.y <= 600

    def Shoot(self, request, context):
        id_shot_by = request.player_id
        player = self.players.get(id_shot_by)
        if not player:
            return game_pb2.ShootResponse(success=False)
         
        bullet = game_pb2.Bullet(
            position=game_pb2.Vec2(x=player.position.x, y=player.position.y),
            direction=game_pb2.Vec2(x=math.cos(player.direction), y=math.sin(player.direction)),
            owner_id=id_shot_by,
            bullet_id=self.bullet_id_counter
        )

        self.bullet_id_counter += 1

        self.bullets.append(bullet)
        return game_pb2.ShootResponse(success=True)

    def create_map_proto_object(self, map_name='map.json'):
        with open(map_name, 'r') as f:
            map_file = json.load(f)
        if 'map' not in map_file or 'colors' not in map_file:
            logger.error("Incorrect map format!")   
            return None
        color_map = [
            game_pb2.ColorMapEntry(
                color=game_pb2.Color(r=color[0], g=color[1], b=color[2]), 
                identifier=identifier
            )
            for identifier, color in map_file['colors'].items()
        ]
        map_proto = game_pb2.Map(color_map=color_map, map=map_file['map'])
        return map_proto

def handle_console(server, servicer):
    global RUNNING
    while RUNNING:
        raw_command = input().strip()
        command, *args = raw_command.split()
        command = command.lower()
        if command == 'exit':
            logger.info("Stopping server...")
            RUNNING = False
            server.stop(0)
            break
        elif command == 'kick':
            if len(args) != 1:
                logger.error("Usage: kick <player_id>")
                continue
            player_id = args[0]
            if player_id not in servicer.players:
                logger.error(f"Player {player_id} not found.")
                continue
            logger.info(f"Kicked player {player_id}.")
            del servicer.players[player_id]
        elif command == 'reloadmap':
            servicer.map_proto = servicer.create_map_proto_object()
            logger.info("Map reloaded!")
        else:
            logger.error(f"Unknown command: {command}")


def serve():
    servicer = GameServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    game_pb2_grpc.add_GameServicer_to_server(servicer, server)
    server.add_insecure_port('[::]:12345')
    server.start()
    logger.info("Server started on port 12345")
    threading.Thread(target=handle_console, args=[server, servicer]).start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
