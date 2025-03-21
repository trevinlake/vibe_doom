import pygame
import numpy as np
import math
import random

# Initialize Pygame
pygame.init()

# Game Settings
WIDTH, HEIGHT = 800, 600
FOV = math.pi / 3  # Field of View
NUM_RAYS = 120  # Number of rays cast
MAX_DEPTH = 800  # Max rendering distance
TILE_SIZE = 50  # Size of each tile
PLAYER_SPEED = 3  # Movement speed
ROTATION_SPEED = 0.05  # Rotation speed
RELOAD_TIME = 60  # Frames to reload

LEVELS = [
    [
        "#########",
        "#.......#",
        "#.#####.#",
        "#.#...#.#",
        "#.#.#.#.#",
        "#...#.#.#",
        "#####.#.#",
        "#.......#",
        "#########"
    ],
    [
        "########",
        "#......#",
        "#.####.#",
        "#.#..#.#",
        "#.#..#.#",
        "#.####.#",
        "#......#",
        "########"
    ]
    
]

current_level = 0
MAP = LEVELS[current_level]

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (92, 28, 3)
DARK_GRAY = (50, 50, 50)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
BROWN = (139, 69, 19)

# Load weapon image
weapon_image = pygame.image.load("weapon.png")
weapon_image = pygame.transform.scale(weapon_image, (100, 100))

# Initialize Display
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)

bullets = []
reload_timer = 0

class Bullet:
    def __init__(self, x, y, angle):
        self.x = x + 25 * math.cos(angle)  # Adjusted to fire from weapon top center
        self.y = y - 50 + HEIGHT - 120  # Adjusted to fire from top of weapon image
        self.angle = angle
        self.speed = 10
        self.active = True
        print(f"Bullet fired from ({self.x}, {self.y}) at angle {self.angle}")

    def move(self):
        if self.active:
            new_x = self.x + self.speed * math.cos(self.angle)
            new_y = self.y + self.speed * math.sin(self.angle)
            map_x, map_y = int(new_x // TILE_SIZE), int(new_y // TILE_SIZE)
            if 0 <= map_y < len(MAP) and 0 <= map_x < len(MAP[0]) and MAP[map_y][map_x] != "#":
                self.x, self.y = new_x, new_y
                print(f"Bullet moved to ({self.x}, {self.y})")
            else:
                print("Bullet hit a wall and stopped")
                self.active = False

    def draw(self):
        if self.active:
            pygame.draw.circle(screen, BROWN, (int(self.x), int(self.y)), 5)


def cast_rays(player_x, player_y, player_angle):
    for ray in range(NUM_RAYS):
        angle = player_angle - FOV / 2 + (FOV / NUM_RAYS) * ray
        for depth in range(1, MAX_DEPTH):
            target_x = player_x + depth * math.cos(angle)
            target_y = player_y + depth * math.sin(angle)
            map_x, map_y = int(target_x // TILE_SIZE), int(target_y // TILE_SIZE)
            
            if 0 <= map_y < len(MAP) and 0 <= map_x < len(MAP[0]):
                if MAP[map_y][map_x] == "#":
                    wall_height = min(HEIGHT, HEIGHT / (depth * 0.01 + 1))
                    pygame.draw.rect(screen, RED, (ray * (WIDTH // NUM_RAYS), (HEIGHT - wall_height) // 2, WIDTH // NUM_RAYS, wall_height))
                    break


def draw_hud(player_health, player_ammo):
    health_text = font.render(f"Health: {player_health}", True, WHITE)
    ammo_text = font.render(f"Ammo: {player_ammo}", True, WHITE)
    screen.blit(health_text, (20, HEIGHT - 50))
    screen.blit(ammo_text, (20, HEIGHT - 25))


def main():
    global running, reload_timer
    running = True
    player_x, player_y = 100, 100  # Ensure the player starts in an open area
    player_angle = 0
    player_health = 100
    player_ammo = 10
    
    print("Game started")

    while running:
        screen.fill(BLACK)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("Quit event detected")
                running = False
            elif (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE) or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                if player_ammo > 0:
                    bullets.append(Bullet(WIDTH // 2, HEIGHT - 120, player_angle))
                    player_ammo -= 1
                elif player_ammo == 0 and reload_timer == 0:
                    reload_timer = RELOAD_TIME

        keys = pygame.key.get_pressed()
        new_x, new_y = player_x, player_y
        if keys[pygame.K_w]:
            new_x += PLAYER_SPEED * math.cos(player_angle)
            new_y += PLAYER_SPEED * math.sin(player_angle)
        if keys[pygame.K_s]:
            new_x -= PLAYER_SPEED * math.cos(player_angle)
            new_y -= PLAYER_SPEED * math.sin(player_angle)
        if keys[pygame.K_a]:
            player_angle -= ROTATION_SPEED
        if keys[pygame.K_d]:
            player_angle += ROTATION_SPEED

        map_x, map_y = int(new_x // TILE_SIZE), int(new_y // TILE_SIZE)
        print(f"Checking collision at {map_x}, {map_y}")
        if 0 <= map_y < len(MAP) and 0 <= map_x < len(MAP[0]) and MAP[map_y][map_x] != "#":
            player_x, player_y = new_x, new_y
            print(f"Player moved to {player_x}, {player_y}")
        else:
            print("Collision detected, movement blocked")

        if reload_timer > 0:
            reload_timer -= 1
            if reload_timer == 0:
                player_ammo = 10

        cast_rays(player_x, player_y, player_angle)
        draw_hud(player_health, player_ammo)

        for bullet in bullets:
            bullet.move()
            bullet.draw()

        screen.blit(weapon_image, (WIDTH // 2 - 50, HEIGHT - 120))

        pygame.display.flip()
        clock.tick(60)

    print("Game exiting")
    pygame.quit()


if __name__ == "__main__":
    main()

