"""
Bubble Typing Game
==================
A polished typing game built with Pygame and a Tkinter start menu.

Bubbles carrying letters A-Z fall from the top of the screen. Press the
matching keyboard key to pop a bubble and score points. If a bubble reaches
the bottom, you lose a life. The game speeds up as your score grows.

INSTALL
-------
    pip install pygame

RUN
---
    python bubble_typing_game.py

Controls
--------
    A-Z  : pop the matching bubble
    Shift : pause / resume
    Ctrl+R: restart (after game over)
    F11  : toggle fullscreen
    ESC  : quit

Game events (start, pause, level up, life lost, game over, ...) are written
to the console and to `logs/bubble_game.log` within the project.
"""

import os
import random
import sys
import math
import logging
import tkinter as tk
from tkinter import messagebox

import pygame

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 800, 600          # Logical render resolution (scaled to screen)
FPS = 60                          # Frames per second
BUBBLE_RADIUS = 32                # Radius of each bubble
SPAWN_INTERVAL_MS = 1100          # Initial time between spawns (ms)
MIN_SPAWN_INTERVAL_MS = 450       # Fastest spawn rate at high levels
BASE_SPEED = 1.4                  # Initial downward speed (px/frame)
SPEED_PER_LEVEL = 0.45            # Speed added per level
POINTS_PER_POP = 10               # Score gained per pop
START_LIVES = 5                   # Starting number of lives
LEVEL_UP_EVERY = 100              # Score needed to advance a level

# A pleasant palette (R, G, B)
COLOR_BG_TOP = (25, 35, 70)       # Gradient top
COLOR_BG_BOTTOM = (10, 15, 35)    # Gradient bottom
COLOR_PANEL = (15, 22, 45)        # HUD panel
COLOR_TEXT = (235, 240, 255)
COLOR_TEXT_DIM = (150, 160, 195)
COLOR_ACCENT = (90, 180, 255)
COLOR_BUBBLE_BORDER = (255, 255, 255)
COLOR_BUBBLE_TEXT = (20, 30, 60)
COLOR_HEART = (235, 70, 90)
COLOR_POP = (255, 220, 120)

# A small palette of bubble fill colors for variety
BUBBLE_COLORS = [
    (255, 120, 130), (120, 200, 255), (160, 255, 170),
    (255, 200, 110), (200, 140, 255), (110, 240, 230),
    (255, 160, 220), (180, 255, 120),
]

# ---------------------------------------------------------------------------
# Logging / paths (frozen-aware for PyInstaller bundles)
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Running as a PyInstaller exe: read-only assets live in _MEIPASS,
    # but logs must be written next to the executable (persistent, writable).
    ASSETS_DIR = os.path.join(sys._MEIPASS, "assets")
    BASE_DIR = os.path.dirname(sys.executable)
else:
    ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "bubble_game.log")
ICON_FILE = os.path.join(ASSETS_DIR, "logo.png")

log = logging.getLogger("bubble_game")


def setup_logging():
    """Configure game logging to both the console and `logs/bubble_game.log`."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("bubble_game")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_gradient(width, height, top_color, bottom_color):
    """Return a Surface with a vertical gradient from top_color to bottom_color."""
    surface = pygame.Surface((width, height))
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (width, y))
    return surface


def ease_out_cubic(t):
    """Cubic ease-out used for the pop animation."""
    return 1 - (1 - t) ** 3


# ---------------------------------------------------------------------------
# Game entities
# ---------------------------------------------------------------------------
class Bubble:
    """A single falling bubble that carries one uppercase letter."""

    def __init__(self, x, letter, speed, color):
        self.x = x
        self.y = -BUBBLE_RADIUS            # start just above the screen
        self.letter = letter               # single character, e.g. "G"
        self.speed = speed                 # px per frame
        self.color = color
        self.radius = BUBBLE_RADIUS
        self.alive = True
        # Pre-render the bubble sprite once for smooth, cheap drawing.
        self.sprite = self._build_sprite()

    def _build_sprite(self):
        """Render a glossy bubble (with highlight) to a transparent Surface."""
        size = self.radius * 2 + 4
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2

        # Soft outer glow
        for i in range(6, 0, -1):
            alpha = int(40 * (1 - i / 6))
            pygame.draw.circle(surf, (*self.color, alpha), (cx, cy), self.radius + i)

        # Main body
        pygame.draw.circle(surf, self.color, (cx, cy), self.radius)
        # White border
        pygame.draw.circle(surf, COLOR_BUBBLE_BORDER, (cx, cy), self.radius, 3)

        # Glossy highlight (top-left)
        highlight = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(highlight, (255, 255, 255, 90),
                           (cx - self.radius // 3, cy - self.radius // 3),
                           self.radius // 2)
        surf.blit(highlight, (0, 0))

        return surf

    def update(self):
        """Move the bubble downward."""
        self.y += self.speed

    def draw(self, surface, font):
        """Blit the bubble sprite and its letter onto the target surface."""
        rect = self.sprite.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(self.sprite, rect)
        letter_surf = font.render(self.letter, True, COLOR_BUBBLE_TEXT)
        surface.blit(letter_surf, letter_surf.get_rect(center=(int(self.x), int(self.y))))

    def is_off_screen(self):
        """True once the bubble has fully passed the bottom edge."""
        return self.y - self.radius > HEIGHT


class Particle:
    """A short-lived particle used for the pop (blast) effect."""

    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size")

    def __init__(self, x, y, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(2.0, 6.0)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.max_life = random.uniform(0.35, 0.6)
        self.life = self.max_life
        self.color = color
        self.size = random.randint(3, 6)

    def update(self, dt):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15            # slight gravity
        self.life -= dt

    def draw(self, surface):
        if self.life <= 0:
            return
        t = self.life / self.max_life
        alpha = int(255 * ease_out_cubic(t))
        size = max(1, int(self.size * t))
        s = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (size, size), size)
        surface.blit(s, (int(self.x - size), int(self.y - size)))

    @property
    def alive(self):
        return self.life > 0


class PopRing:
    """An expanding ring drawn when a bubble is popped."""

    __slots__ = ("x", "y", "life", "max_life", "color")

    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.max_life = 0.35
        self.life = self.max_life
        self.color = color

    def update(self, dt):
        self.life -= dt

    def draw(self, surface):
        if self.life <= 0:
            return
        t = 1 - self.life / self.max_life
        radius = int(BUBBLE_RADIUS + 40 * ease_out_cubic(t))
        alpha = int(220 * (1 - t))
        size = radius * 2 + 4
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (size // 2, size // 2), radius, 3)
        surface.blit(s, (int(self.x - size // 2), int(self.y - size // 2)))

    @property
    def alive(self):
        return self.life > 0


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------
class BubbleTypingGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Bubble Typing Game")
        # Use the project logo as the window/taskbar icon when available.
        if os.path.exists(ICON_FILE):
            try:
                pygame.display.set_icon(pygame.image.load(ICON_FILE))
            except Exception:
                pass
        # Full display: SCALED keeps the 800x600 logical resolution while
        # stretching it to fill the monitor crisply.
        self.fullscreen = True
        self.screen = pygame.display.set_mode(
            (WIDTH, HEIGHT), pygame.SCALED | pygame.FULLSCREEN
        )
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_letter = pygame.font.SysFont("arial", 26, bold=True)
        self.font_hud = pygame.font.SysFont("arial", 22, bold=True)
        self.font_big = pygame.font.SysFont("arial", 56, bold=True)
        self.font_mid = pygame.font.SysFont("arial", 32, bold=True)
        self.font_small = pygame.font.SysFont("arial", 18)

        # Cached background gradient
        self.background = make_gradient(WIDTH, HEIGHT, COLOR_BG_TOP, COLOR_BG_BOTTOM)

        self.reset()

    # -- display ------------------------------------------------------------
    def toggle_fullscreen(self):
        """Switch between fullscreen and windowed mode."""
        self.fullscreen = not self.fullscreen
        flags = pygame.SCALED | pygame.FULLSCREEN if self.fullscreen else pygame.SCALED
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        log.info("Fullscreen %s", "ON" if self.fullscreen else "OFF")

    # -- state management ---------------------------------------------------
    def reset(self):
        """Reset all gameplay state for a fresh run."""
        self.bubbles = []
        self.particles = []
        self.rings = []
        self.score = 0
        self.lives = START_LIVES
        self.level = 1
        self.spawn_timer = 0
        self.game_over = False
        self.paused = False
        self.shake = 0                     # screen-shake intensity
        self.flash = 0                     # red flash when losing a life
        log.info("Game reset -> score=0 lives=%d level=1", START_LIVES)

    @property
    def spawn_interval(self):
        """Spawn interval shrinks as the level rises."""
        return max(MIN_SPAWN_INTERVAL_MS, SPAWN_INTERVAL_MS - (self.level - 1) * 80)

    @property
    def bubble_speed(self):
        """Downward speed grows with level."""
        return BASE_SPEED + (self.level - 1) * SPEED_PER_LEVEL

    # -- spawning -----------------------------------------------------------
    def spawn_bubble(self):
        letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        # Keep the bubble fully on-screen horizontally.
        x = random.randint(BUBBLE_RADIUS + 6, WIDTH - BUBBLE_RADIUS - 6)
        color = random.choice(BUBBLE_COLORS)
        self.bubbles.append(Bubble(x, letter, self.bubble_speed, color))

    # -- input --------------------------------------------------------------
    def handle_key(self, key_char):
        """Pop the lowest matching bubble when the player presses a letter."""
        if self.game_over or self.paused:
            return
        key_char = key_char.upper()
        # Find matching bubbles; pop the one closest to the bottom first
        # (the most "urgent" threat) for satisfying gameplay.
        candidates = [b for b in self.bubbles if b.alive and b.letter == key_char]
        if not candidates:
            log.debug("Wrong key '%s' (no matching bubble)", key_char)
            return
        target = max(candidates, key=lambda b: b.y)
        self.pop_bubble(target)

    def pop_bubble(self, bubble):
        """Destroy a bubble, award points, and spawn visual effects."""
        bubble.alive = False
        self.score += POINTS_PER_POP
        log.debug("Popped '%s' -> score=%d", bubble.letter, self.score)

        # Particle burst
        for _ in range(18):
            self.particles.append(Particle(bubble.x, bubble.y, bubble.color))
        self.rings.append(PopRing(bubble.x, bubble.y, COLOR_POP))

        # Level up check
        new_level = 1 + self.score // LEVEL_UP_EVERY
        if new_level > self.level:
            self.level = new_level
            log.info("Level up! Now level %d (speed=%.2f)", self.level, self.bubble_speed)

    def lose_life(self):
        self.lives -= 1
        self.shake = 10
        self.flash = 1.0
        log.info("Life lost -> lives remaining=%d", self.lives)
        if self.lives <= 0:
            self.game_over = True
            log.info("GAME OVER -> final score=%d level=%d", self.score, self.level)

    # -- main loop ----------------------------------------------------------
    def run(self):
        log.info("Game started (fullscreen=%s)", self.fullscreen)
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0   # seconds since last frame

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and not self.game_over:
                        self.paused = not self.paused
                        log.info("Game %s", "paused" if self.paused else "resumed")
                    elif event.key == pygame.K_r and (event.mod & pygame.KMOD_CTRL) and self.game_over:
                        self.reset()
                    elif event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                    elif event.unicode and event.unicode.isalpha():
                        self.handle_key(event.unicode)

            if not self.game_over and not self.paused:
                self.update(dt)

            self.draw()
            pygame.display.flip()

        log.info("Game exited")
        pygame.quit()

    # -- update -------------------------------------------------------------
    def update(self, dt):
        # Spawn new bubbles on a timer
        self.spawn_timer += self.clock.get_time()
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0
            self.spawn_bubble()

        # Move bubbles and detect misses
        for b in self.bubbles:
            b.update()
            if b.is_off_screen():
                b.alive = False
                self.lose_life()

        # Remove dead bubbles
        self.bubbles = [b for b in self.bubbles if b.alive]

        # Update effects
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        for r in self.rings:
            r.update(dt)
        self.rings = [r for r in self.rings if r.alive]

        # Decay shake / flash
        if self.shake > 0:
            self.shake = max(0, self.shake - 30 * dt)
        if self.flash > 0:
            self.flash = max(0, self.flash - 2.0 * dt)

    # -- drawing ------------------------------------------------------------
    def draw(self):
        # Optional screen shake offset
        shake_x = shake_y = 0
        if self.shake > 0:
            shake_x = random.randint(-int(self.shake), int(self.shake))
            shake_y = random.randint(-int(self.shake), int(self.shake))

        # Background
        self.screen.blit(self.background, (shake_x, shake_y))

        # Bubbles
        for b in self.bubbles:
            b.draw(self.screen, self.font_letter)

        # Effects
        for r in self.rings:
            r.draw(self.screen)
        for p in self.particles:
            p.draw(self.screen)

        # HUD
        self.draw_hud()

        # Red flash overlay when a life is lost
        if self.flash > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 60, 60, int(80 * self.flash)))
            self.screen.blit(overlay, (0, 0))

        # Overlays
        if self.paused:
            self.draw_center_overlay("PAUSED", "Press Shift to resume")
        elif self.game_over:
            self.draw_game_over()

    def draw_hud(self):
        """Draw the scoreboard panel: Score, Lives (hearts), Level."""
        panel_h = 56
        panel = pygame.Surface((WIDTH, panel_h), pygame.SRCALPHA)
        panel.fill((*COLOR_PANEL, 210))
        self.screen.blit(panel, (0, 0))

        # Score (left)
        score_text = self.font_hud.render(f"Score: {self.score}", True, COLOR_TEXT)
        self.screen.blit(score_text, (20, 16))

        # Level (right)
        level_text = self.font_hud.render(f"Level: {self.level}", True, COLOR_ACCENT)
        self.screen.blit(level_text, (WIDTH - level_text.get_width() - 20, 16))

        # Lives as hearts (center)
        label = self.font_small.render("Lives:", True, COLOR_TEXT_DIM)
        self.screen.blit(label, (WIDTH // 2 - 70, 20))
        for i in range(START_LIVES):
            filled = i < self.lives
            self.draw_heart(self.screen, WIDTH // 2 + 10 + i * 26, 28, filled)

    def draw_heart(self, surface, x, y, filled):
        """Draw a small heart icon at (x, y)."""
        color = COLOR_HEART if filled else (60, 65, 90)
        # Two circles + a triangle approximates a heart
        r = 8
        pygame.draw.circle(surface, color, (x - r // 2, y - 2), r // 2 + 2)
        pygame.draw.circle(surface, color, (x + r // 2, y - 2), r // 2 + 2)
        pygame.draw.polygon(surface, color, [
            (x - r - 1, y),
            (x + r + 1, y),
            (x, y + r + 4),
        ])

    def draw_center_overlay(self, title, subtitle):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        t = self.font_big.render(title, True, COLOR_TEXT)
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
        s = self.font_mid.render(subtitle, True, COLOR_TEXT_DIM)
        self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30)))

    def draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        title = self.font_big.render("GAME OVER", True, (255, 90, 110))
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 70)))

        score = self.font_mid.render(f"Final Score: {self.score}", True, COLOR_TEXT)
        self.screen.blit(score, score.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10)))

        level = self.font_small.render(f"Reached Level {self.level}", True, COLOR_TEXT_DIM)
        self.screen.blit(level, level.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 25)))

        hint = self.font_mid.render("Press Ctrl+R to Restart   |   ESC to Quit", True, COLOR_ACCENT)
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 75)))


# ---------------------------------------------------------------------------
# Tkinter start menu
# ---------------------------------------------------------------------------
def show_start_menu():
    """Display a Tkinter start screen; return True if the player wants to play."""
    root = tk.Tk()
    root.title("Bubble Typing Game")
    root.configure(bg="#1a2244")
    root.resizable(False, False)

    result = {"play": False}

    def on_start():
        result["play"] = True
        root.destroy()

    def on_quit():
        root.destroy()

    # Logo image (scaled down for the menu). PIL gives the most reliable PNG
    # rendering in tkinter; fall back to tk.PhotoImage if PIL is unavailable.
    logo_img = None
    if os.path.exists(ICON_FILE):
        try:
            from PIL import Image, ImageTk
            pil = Image.open(ICON_FILE).resize((160, 160), Image.LANCZOS)
            logo_img = ImageTk.PhotoImage(pil)
        except Exception:
            try:
                logo_img = tk.PhotoImage(file=ICON_FILE).subsample(4, 4)
            except Exception:
                logo_img = None
        if logo_img is not None:
            root.logo_img = logo_img            # keep reference (avoid GC)
            tk.Label(root, image=logo_img, bg="#1a2244").pack(pady=(30, 8))
            try:
                root.iconphoto(False, logo_img)  # taskbar / title-bar icon
            except Exception:
                pass

    # Title
    title = tk.Label(
        root, text="Bubble Typing Game",
        font=("Helvetica", 24, "bold"), fg="#ffffff", bg="#1a2244"
    )
    title.pack(pady=(4, 10))

    subtitle = tk.Label(
        root, text="Pop the falling bubbles by pressing the matching letter key!",
        font=("Helvetica", 12), fg="#aab4dd", bg="#1a2244"
    )
    subtitle.pack(pady=(0, 25))

    # Instructions box
    instructions = (
        "How to play:\n"
        "  • Bubbles fall from the top, each carrying a letter A–Z.\n"
        "  • Press the matching key to pop a bubble and score points.\n"
        "  • If a bubble reaches the bottom, you lose a life.\n"
        "  • The game speeds up as your score grows.\n\n"
        "Controls:\n"
        "  A–Z  pop bubble   Shift  pause   Ctrl+R  restart\n"
        "  F11  fullscreen   ESC  quit"
    )
    info = tk.Label(
        root, text=instructions, font=("Consolas", 11),
        fg="#dfe6ff", bg="#243056", justify="left", padx=20, pady=16
    )
    info.pack(padx=30, pady=(0, 25))

    # Buttons
    btn_frame = tk.Frame(root, bg="#1a2244")
    btn_frame.pack(pady=(0, 30))

    start_btn = tk.Button(
        btn_frame, text="Start Game", font=("Helvetica", 13, "bold"),
        bg="#5ab4ff", fg="white", activebackground="#3a9eef",
        relief="flat", padx=24, pady=8, command=on_start
    )
    start_btn.grid(row=0, column=0, padx=10)

    quit_btn = tk.Button(
        btn_frame, text="Quit", font=("Helvetica", 13),
        bg="#3a4470", fg="white", activebackground="#2a3460",
        relief="flat", padx=24, pady=8, command=on_quit
    )
    quit_btn.grid(row=0, column=1, padx=10)

    # Center the window on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    root.mainloop()
    return result["play"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    # Set up game logging first so startup is recorded too.
    setup_logging()
    log.info("Launching Bubble Typing Game")

    # Show the Tkinter menu first; launch Pygame only if the player starts.
    if not show_start_menu():
        log.info("Player quit from the start menu")
        sys.exit(0)

    # Verify pygame is available with a friendly message if not.
    try:
        game = BubbleTypingGame()
    except pygame.error as exc:
        log.error("Pygame initialization failed: %s", exc)
        messagebox.showerror("Pygame Error", f"Could not initialize Pygame:\n{exc}")
        sys.exit(1)

    game.run()


if __name__ == "__main__":
    main()
