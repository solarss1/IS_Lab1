import pygame
import sys
import random

# ============================================================
# CONFIGURATION
# ============================================================

CONFIG = {
    "TILE_SIZE": 24,
    "FPS": 60,
    # Fixed movement timing for all difficulties (no speed-based difficulty)
    "PLAYER_STEP_FRAMES": 7,
    "GHOST_STEP_FRAMES": 14,
    # Colors
    "COLORS": {
        "BG": (0, 0, 0),
        "WALL": (10, 10, 80),
        "PACMAN": (255, 255, 0),
        "PELLET": (255, 255, 255),
        "GHOST": (255, 0, 0),
        "TEXT": (255, 255, 255),
        "TITLE": (255, 255, 0),
    },
}

# Map symbols:
# # = wall, . = pellet, P = Pac-Man, G = ghost
LEVEL_MAP = [
    "########################",
    "#..........##...G......#",
    "#.####.###.##.###.####.#",
    "#G####.###.##.###.####G#",
    "#.####.###.##.###.####.#",
    "#......................#",
    "#.####.##.######.##.####",
    "#......##....##....##..#",
    "######.######.######.###",
    "#.....P....##..........#",
    "########################",
]

# Difficulty configs (5 levels)
DIFFICULTIES = {
    "VERY_EASY": {
        "name": "VERY_EASY",
        "desc": "Only random wandering. No intelligence at all.",
        "lives": 7,
        "strategy_cycle": ["random_limited"],
        "rules": {
            "see_maze": True,
            "see_pacman_global": False,
            "see_pacman_los": False,
            "see_other_ghosts": False,
            "share_thoughts": False,
        },
    },

    "EASY": {
        "name": "EASY",
        "desc": "Random/patrol ghosts, no knowledge of Pac-Man.",
        "lives": 5,
        "strategy_cycle": ["random_limited", "patrol"],
        "rules": {
            "see_maze": True,
            "see_pacman_global": False,
            "see_pacman_los": False,
            "see_other_ghosts": False,
            "share_thoughts": False,
        },
    },

    "NORMAL": {
        "name": "NORMAL",
        "desc": "Some ghosts react if Pac-Man is in line-of-sight.",
        "lives": 3,
        "strategy_cycle": ["chase_los", "random_limited", "patrol"],
        "rules": {
            "see_maze": True,
            "see_pacman_global": False,
            "see_pacman_los": True,
            "see_other_ghosts": True,
            "share_thoughts": False,
        },
    },

    "HARD": {
        "name": "HARD",
        "desc": "Some ghosts know Pac-Man globally, but no shared intelligence.",
        "lives": 2,
        "strategy_cycle": ["chase_global", "chase_los", "patrol", "random_limited"],
        "rules": {
            "see_maze": True,
            "see_pacman_global": True,
            "see_pacman_los": True,
            "see_other_ghosts": True,
            "share_thoughts": False,
        },
    },

    "INSANE": {
        "name": "INSANE",
        "desc": "All ghosts fully coordinate with global knowledge of Pac-Man.",
        "lives": 1,
        "strategy_cycle": ["chase_global", "chase_los", "patrol"],
        "rules": {
            "see_maze": True,
            "see_pacman_global": True,
            "see_pacman_los": True,
            "see_other_ghosts": True,
            "share_thoughts": True,  # <<< головна фішка
        },
    },
}


# ============================================================
# UTILS
# ============================================================

def can_move(col, row, level_map):
    if row < 0 or row >= len(level_map):
        return False
    if col < 0 or col >= len(level_map[0]):
        return False
    return level_map[row][col] != "#"


def has_line_of_sight(gc, gr, pc, pr, level_map):
    """Check direct (row/col) visibility without walls."""
    if gc == pc:
        step = 1 if pr > gr else -1
        for r in range(gr + step, pr, step):
            if level_map[r][gc] == "#":
                return False
        return True
    if gr == pr:
        step = 1 if pc > gc else -1
        for c in range(gc + step, pc, step):
            if level_map[gr][c] == "#":
                return False
        return True
    return False


def random_valid_move(gc, gr, level_map):
    moves = []
    for dc, dr in [(-1,0), (1,0), (0,-1), (0,1)]:
        nc, nr = gc + dc, gr + dr
        if can_move(nc, nr, level_map):
            moves.append((dc, dr))
    return random.choice(moves) if moves else (0, 0)


# ============================================================
# GHOST STRATEGIES (PLUGGABLE)
# ============================================================

def strat_random_limited(ghost, player_pos, level_map, ghosts, rules):
    """Local random walk; no Pac-Man knowledge."""
    gc, gr = ghost.col, ghost.row
    dc, dr = random_valid_move(gc, gr, level_map)
    ghost.col += dc
    ghost.row += dr


def strat_patrol(ghost, player_pos, level_map, ghosts, rules):
    """
    Horizontal-biased patrol; no Pac-Man knowledge.
    If blocked, tries alternatives; never permanently stuck.
    """
    gc, gr = ghost.col, ghost.row

    # All valid moves
    valid = []
    for dc, dr in [(-1,0), (1,0), (0,-1), (0,1)]:
        nc, nr = gc + dc, gr + dr
        if can_move(nc, nr, level_map):
            valid.append((dc, dr))
    if not valid:
        return

    horiz = [d for d in valid if d in [(-1,0), (1,0)]]
    vert  = [d for d in valid if d in [(0,-1), (0,1)]]

    # If current dir invalid -> pick new
    if ghost.dir not in valid:
        if horiz:
            ghost.dir = random.choice(horiz)
        elif vert:
            ghost.dir = random.choice(vert)
        else:
            ghost.dir = random.choice(valid)
    else:
        dc, dr = ghost.dir
        nc, nr = gc + dc, gr + dr
        if not can_move(nc, nr, level_map):
            if horiz:
                ghost.dir = random.choice(horiz)
            elif vert:
                ghost.dir = random.choice(vert)
            else:
                ghost.dir = random.choice(valid)

    dc, dr = ghost.dir
    ghost.col += dc
    ghost.row += dr


def strat_chase_los(ghost, player_pos, level_map, ghosts, rules):
    """
    Chase only if Pac-Man is visible in a straight line.
    Otherwise fallback to local random movement.
    """
    if not rules.get("see_pacman_los", False):
        return strat_random_limited(ghost, player_pos, level_map, ghosts, rules)

    gc, gr = ghost.col, ghost.row
    pc, pr = player_pos

    if has_line_of_sight(gc, gr, pc, pr, level_map):
        best_dc, best_dr = 0, 0
        best_dist = abs(gc - pc) + abs(gr - pr)
        for dc, dr in [(-1,0), (1,0), (0,-1), (0,1)]:
            nc, nr = gc + dc, gr + dr
            if can_move(nc, nr, level_map):
                d = abs(nc - pc) + abs(nr - pr)
                if d < best_dist:
                    best_dist = d
                    best_dc, best_dr = dc, dr
        if best_dc or best_dr:
            ghost.col += best_dc
            ghost.row += best_dr
            return

    strat_random_limited(ghost, player_pos, level_map, ghosts, rules)


def strat_chase_global(ghost, player_pos, level_map, ghosts, rules):
    """
    Greedy chase with global Pac-Man info.
    Only allowed when see_pacman_global=True.
    Extra: if share_thoughts=True, ghosts try to agree on a common move
    (most-voted best move) to simulate coordinated behavior.
    """
    if not rules.get("see_pacman_global", False):
        return strat_chase_los(ghost, player_pos, level_map, ghosts, rules)

    gc, gr = ghost.col, ghost.row
    pc, pr = player_pos

    # If share_thoughts enabled -> compute majority preferred move across ghosts
    if rules.get("share_thoughts", False) and ghosts:
        # For each ghost compute its own best move (or (0,0) if none)
        votes = {}
        preferred_for_this = None
        for g in ghosts:
            g_gc, g_gr = g.col, g.row
            best_dc, best_dr = None, None
            best_dist = abs(g_gc - pc) + abs(g_gr - pr)
            for dc, dr in [(-1,0), (1,0), (0,-1), (0,1)]:
                nc, nr = g_gc + dc, g_gr + dr
                if can_move(nc, nr, level_map):
                    d = abs(nc - pc) + abs(nr - pr)
                    if d < best_dist:
                        best_dist = d
                        best_dc, best_dr = dc, dr
            if best_dc is None and best_dr is None:
                move = (0, 0)
            else:
                move = (best_dc, best_dr)
            votes[move] = votes.get(move, 0) + 1

            # also remember this ghost's preferred move if it's this ghost
            if g is ghost:
                preferred_for_this = move

        # choose majority move (highest votes). tie-breaker: prefer this ghost's preferred
        majority_move = max(votes.items(), key=lambda kv: (kv[1], kv[0]))[0]

        # If majority_move is valid for THIS ghost, use it; else fallback to preferred_for_this or random
        if majority_move != (0, 0):
            dc, dr = majority_move
            nc, nr = gc + dc, gr + dr
            if can_move(nc, nr, level_map):
                ghost.col += dc
                ghost.row += dr
                return

        # try preferred_for_this if available and valid
        if preferred_for_this and preferred_for_this != (0, 0):
            dc, dr = preferred_for_this
            nc, nr = gc + dc, gr + dr
            if can_move(nc, nr, level_map):
                ghost.col += dc
                ghost.row += dr
                return

        # fallback random
        dc, dr = random_valid_move(gc, gr, level_map)
        ghost.col += dc
        ghost.row += dr
        return

    # Default non-shared greedy chase
    best_dc, best_dr = 0, 0
    best_dist = abs(gc - pc) + abs(gr - pr)

    for dc, dr in [(-1,0), (1,0), (0,-1), (0,1)]:
        nc, nr = gc + dc, gr + dr
        if can_move(nc, nr, level_map):
            d = abs(nc - pc) + abs(nr - pr)
            if d < best_dist:
                best_dist = d
                best_dc, best_dr = dc, dr

    if best_dc or best_dr:
        ghost.col += best_dc
        ghost.row += best_dr
    else:
        strat_random_limited(ghost, player_pos, level_map, ghosts, rules)


GHOST_STRATEGIES = {
    "random_limited": strat_random_limited,
    "patrol": strat_patrol,
    "chase_los": strat_chase_los,
    "chase_global": strat_chase_global,
}


# ============================================================
# GHOST CLASS
# ============================================================

class Ghost:
    def __init__(self, col, row, strategy_name="random_limited"):
        self.col = col
        self.row = row
        self.spawn = (col, row)
        self.strategy_name = strategy_name
        self.dir = (0, 0)  # for patrol

    def step(self, player_pos, level_map, ghosts, rules):
        func = GHOST_STRATEGIES.get(self.strategy_name, strat_random_limited)
        func(self, player_pos, level_map, ghosts, rules)

    def reset(self):
        self.col, self.row = self.spawn
        self.dir = (0, 0)


# ============================================================
# LEVEL LOADING (PURE FUNCTION, CONFIG-BASED)
# ============================================================

def load_level(level_map, difficulty_config):
    """Return walls, pellets, player_pos, player_spawn, ghosts based on given difficulty."""
    tile = CONFIG["TILE_SIZE"]
    walls = []
    pellets = set()
    player_pos = None
    player_spawn = None
    ghosts = []

    strategy_cycle = difficulty_config["strategy_cycle"]
    si = 0

    for r, row in enumerate(level_map):
        for c, ch in enumerate(row):
            x = c * tile
            y = r * tile
            if ch == "#":
                walls.append(pygame.Rect(x, y, tile, tile))
            elif ch == ".":
                pellets.add((c, r))
            elif ch == "P":
                player_pos = [c, r]
                player_spawn = [c, r]
            elif ch == "G":
                strat = strategy_cycle[si % len(strategy_cycle)]
                si += 1
                ghosts.append(Ghost(c, r, strat))

    return walls, pellets, player_pos, player_spawn, ghosts


# ============================================================
# GAME CLASS (MODULAR)
# ============================================================

class Game:
    def __init__(self, level_map, difficulties, config):
        self.level_map = level_map
        self.difficulties = difficulties
        self.cfg = config

        self.width = len(level_map[0]) * config["TILE_SIZE"]
        self.height = len(level_map) * config["TILE_SIZE"]

        self.screen = None
        self.clock = None
        self.font_big = None
        self.font = None
        self.font_small = None

        self.reset_to_menu()

    # --------- STATE MANAGEMENT ---------

    def reset_to_menu(self):
        self.selecting_difficulty = True
        self.current_diff_name = None
        self.current_diff = None

        self.walls = []
        self.pellets = set()
        self.player_pos = [0, 0]
        self.player_spawn = [0, 0]
        self.ghosts = []

        self.dir_col = 0
        self.dir_row = 0
        self.lives = 0
        self.score = 0

        self.game_over = False
        self.win = False

        self.player_step_counter = 0
        self.ghost_step_counter = 0

    def apply_difficulty(self, diff_name):
        self.current_diff_name = diff_name
        self.current_diff = self.difficulties[diff_name]
        self.walls, self.pellets, self.player_pos, self.player_spawn, self.ghosts = load_level(
            self.level_map, self.current_diff
        )
        self.dir_col = self.dir_row = 0
        self.lives = self.current_diff["lives"]
        self.score = 0
        self.game_over = self.win = False
        self.player_step_counter = self.ghost_step_counter = 0
        self.selecting_difficulty = False

    # --------- EVENT HANDLING ---------

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                if self.selecting_difficulty:
                    self._handle_menu_key(event.key)
                else:
                    self._handle_game_key(event.key)

    def _handle_menu_key(self, key):
        # Map 0..4 to the 5 difficulties
        if key == pygame.K_0:
            self.apply_difficulty("VERY_EASY")
        elif key == pygame.K_1:
            self.apply_difficulty("EASY")
        elif key == pygame.K_2:
            self.apply_difficulty("NORMAL")
        elif key == pygame.K_3:
            self.apply_difficulty("HARD")
        elif key == pygame.K_4:
            self.apply_difficulty("INSANE")

    def _handle_game_key(self, key):
        if key == pygame.K_LEFT:
            self.dir_col, self.dir_row = -1, 0
        elif key == pygame.K_RIGHT:
            self.dir_col, self.dir_row = 1, 0
        elif key == pygame.K_UP:
            self.dir_col, self.dir_row = 0, -1
        elif key == pygame.K_DOWN:
            self.dir_col, self.dir_row = 0, 1
        elif key == pygame.K_r:
            # Back to difficulty selection
            self.reset_to_menu()
            return

        # Restart after win/lose with same difficulty
        if (self.game_over or self.win) and key != pygame.K_r:
            self.apply_difficulty(self.current_diff_name)

    # --------- UPDATE LOGIC ---------

    def update(self):
        if self.selecting_difficulty or self.game_over or self.win:
            return

        self._update_player()
        self._update_ghosts()
        self._check_collisions()
        self._check_win()

    def _update_player(self):
        self.player_step_counter += 1
        if self.player_step_counter < self.cfg["PLAYER_STEP_FRAMES"]:
            return
        self.player_step_counter = 0

        nc = self.player_pos[0] + self.dir_col
        nr = self.player_pos[1] + self.dir_row
        if can_move(nc, nr, self.level_map):
            self.player_pos = [nc, nr]

        if (self.player_pos[0], self.player_pos[1]) in self.pellets:
            self.pellets.remove((self.player_pos[0], self.player_pos[1]))
            self.score += 10

    def _update_ghosts(self):
        self.ghost_step_counter += 1
        if self.ghost_step_counter < self.cfg["GHOST_STEP_FRAMES"]:
            return
        self.ghost_step_counter = 0

        rules = self.current_diff["rules"]
        for ghost in self.ghosts:
            ghost.step(self.player_pos, self.level_map, self.ghosts, rules)

    def _check_collisions(self):
        for ghost in self.ghosts:
            if ghost.col == self.player_pos[0] and ghost.row == self.player_pos[1]:
                self.lives -= 1
                if self.lives > 0:
                    self._reset_positions_after_hit()
                else:
                    self.game_over = True
                break

    def _reset_positions_after_hit(self):
        self.player_pos = self.player_spawn.copy()
        for g in self.ghosts:
            g.reset()
        self.dir_col = self.dir_row = 0
        self.player_step_counter = self.ghost_step_counter = 0

    def _check_win(self):
        if not self.pellets and not self.game_over:
            self.win = True

    # --------- DRAWING ---------

    def draw(self):
        colors = self.cfg["COLORS"]
        self.screen.fill(colors["BG"])

        if self.selecting_difficulty:
            self._draw_menu()
        else:
            self._draw_game()

        pygame.display.flip()

    def _draw_menu(self):
        colors = self.cfg["COLORS"]
        title = self.font_big.render("Оберіть рівень складності", True, colors["TITLE"])
        self.screen.blit(title, (self.width//2 - title.get_width()//2, self.height//2 - 140))

        y = self.height//2 - 80
        options = [("0", "VERY_EASY"), ("1", "EASY"), ("2", "NORMAL"), ("3", "HARD"), ("4", "INSANE")]
        for key, name in options:
            diff = self.difficulties[name]
            line = self.font.render(f"{key} - {name}", True, colors["TEXT"])
            self.screen.blit(line, (self.width//2 - line.get_width()//2, y))
            y += 28
            desc = self.font_small.render(diff["desc"], True, colors["TEXT"])
            self.screen.blit(desc, (self.width//2 - desc.get_width()//2, y))
            y += 32

        hint = self.font_small.render("Натисніть 0 / 1 / 2 / 3 / 4. ESC - вихід.", True, colors["TEXT"])
        self.screen.blit(hint, (self.width//2 - hint.get_width()//2, y + 10))

    def _draw_game(self):
        colors = self.cfg["COLORS"]
        tile = self.cfg["TILE_SIZE"]

        # Walls
        for w in self.walls:
            pygame.draw.rect(self.screen, colors["WALL"], w)

        # Pellets
        for (c, r) in self.pellets:
            x = c * tile + tile // 2
            y = r * tile + tile // 2
            pygame.draw.circle(self.screen, colors["PELLET"], (x, y), 4)

        # Pac-Man
        px = self.player_pos[0] * tile + tile // 2
        py = self.player_pos[1] * tile + tile // 2
        pygame.draw.circle(self.screen, colors["PACMAN"], (px, py), tile // 2 - 2)

        # Ghosts
        for ghost in self.ghosts:
            gx = ghost.col * tile + tile // 2
            gy = ghost.row * tile + tile // 2
            pygame.draw.circle(self.screen, colors["GHOST"], (gx, gy), tile // 2 - 2)

        # HUD
        rules = self.current_diff["rules"]
        hud = self.font_small.render(
            f"Mode: {self.current_diff_name} | Score: {self.score} | Lives: {self.lives} | Pellets: {len(self.pellets)}",
            True,
            colors["TEXT"],
        )
        self.screen.blit(hud, (10, 5))

        # Show ghost strategies
        strat_info = ", ".join(f"{i}:{g.strategy_name}" for i, g in enumerate(self.ghosts))
        strat_text = self.font_small.render(f"Ghosts: {strat_info}", True, colors["TEXT"])
        self.screen.blit(strat_text, (10, self.height - 40))

        # Show active rule subset (for report)
        rule_text = self.font_small.render(
            f"Rules: LOS={rules['see_pacman_los']} Global={rules['see_pacman_global']} Shared={rules['share_thoughts']}",
            True,
            colors["TEXT"],
        )
        self.screen.blit(rule_text, (10, self.height - 20))

        if self.game_over:
            txt = self.font.render("Game Over! Any key - restart | R - меню", True, colors["TEXT"])
            self.screen.blit(txt, (self.width//2 - txt.get_width()//2, self.height//2 - 10))
        elif self.win:
            txt = self.font.render("You Win! Any key - restart | R - меню", True, colors["TEXT"])
            self.screen.blit(txt, (self.width//2 - txt.get_width()//2, self.height//2 - 10))

    # --------- MAIN LOOP ---------

    def run(self):
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Pac-Man: Modular Rule-Based Difficulty")
        self.clock = pygame.time.Clock()

        self.font_big = pygame.font.SysFont("arial", 32, bold=True)
        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.font_small = pygame.font.SysFont("arial", 16)

        while True:
            self.clock.tick(self.cfg["FPS"])
            self.handle_events()
            self.update()
            self.draw()


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    game = Game(LEVEL_MAP, DIFFICULTIES, CONFIG)
    game.run()


if __name__ == "__main__":
    main()