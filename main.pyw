############## INITIALIZATION ##############

import pygame as pg
import easing_functions as easing
import copy
import draw
from typing import List
import clipboard

pg.init()

windowx = 1280
windowy = 720
clock = pg.time.Clock()
fps = 60

screen = pg.display.set_mode((windowx,windowy), pg.RESIZABLE)
running = True
pg.display.set_caption('Pesok Sim')
draw.def_surface = screen

halfx = windowx//2
halfy = windowy//2

# app classes

class Tile:
    def __init__(self, x, y, dir):
        self.powered = False
        self.direction = dir
        self.pos = [int(x), int(y)]

    @property
    def x(self):
        return int(self.pos[0])

    @property
    def y(self):
        return int(self.pos[1])
    
    def can_power(self, offset):
        if not self.powered: return False
        if offset != self.direction: return False
        return True

    def can_be_powered(self, offset):
        return True
    

class Wire(Tile):
    name = 'Wire'
    description = 'Transfers signal from its back to its front.'
    color = (60,25,25)
    power_color = (255,70,70)

    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)

class Splitter(Tile):
    name = 'Splitter'
    description = 'Transfers signal from its back to everywhere except its back and tiles adjacent to its back.'
    color = (75,50,50)
    power_color = (200,140,140)

    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
    
    def can_power(self, offset):
        if not self.powered: return False
        if self.direction in get_adjacent([-offset[0], -offset[1]]):
            return False
        return True
    
class Emitter(Tile):
    name = 'Emitter'
    description = 'Emits constant signal from its front. Cannot be turned off.'
    color = (255,160,160)
    power_color = (255,160,160)
    
    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
        self.powered = True

    def can_be_powered(self, offset):
        return False
    
    def can_power(self, offset):
        if offset != self.direction: return False
        return True
    
class Threader(Tile):
    name = 'Threader'
    description = 'Splits the incoming signal to the sides adjacent to its front.'
    color = (0,32,128)
    power_color = (0,64,255)
    
    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
        self.powered = False
    
    def can_power(self, offset):
        if not self.powered: return False
        if self.direction in get_adjacent(offset, False):
            return True
        return False
    
class Not(Tile):
    name = 'Not Gate'
    description = 'Emits a signal from its front if it doesn\'t receive power from its back.'
    color = (64,64,64)
    power_color = (192,192,192)

    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
    
    def can_power(self, offset):
        if self.powered: return False
        if offset != self.direction: return False
        return True
    

class Grid:
    def __init__(self):
        self.tiles: List[Tile] = []

    def find(self, pos):
        for i in self.tiles:
            if i.pos == pos:
                return i
        return None
    
    def table(self):
        table = dict()
        for i in self.tiles:
            table[f'{i.x} {i.y}'] = copy.deepcopy(i)
        return table

    def place(self, class_type, pos, direction):
        if self.find(pos) == None:
            self.tiles.append(class_type(pos[0], pos[1], direction)) 

    def erase(self, pos):
        tile = self.find(pos)
        if tile != None:
            self.tiles.remove(tile) 

    def tick(self):
        queue = []
        table = self.table()

        for i in self.tiles:
            pos = i.pos
            poses = [
                [pos[0], pos[1]+1],
                [pos[0], pos[1]-1],
                [pos[0]+1, pos[1]],
                [pos[0]-1, pos[1]],
                [pos[0]+1, pos[1]+1],
                [pos[0]+1, pos[1]-1],
                [pos[0]-1, pos[1]+1],
                [pos[0]-1, pos[1]-1],
            ]
            powered = False
            for pos in poses:
                intpos = pos
                pos = f'{pos[0]} {pos[1]}'
                offset = [intpos[0]-i.x, intpos[1]-i.y]
                if pos in table:
                    elem = table[pos]
                    if i.can_be_powered(offset):
                        if elem.can_power([-offset[0], -offset[1]]):
                            powered = True
                            break
            i.powered = powered
            queue.append(i)
        self.tiles = queue
            

class App:
    def __init__(self, save_name='Untitled'):
        self.grid: Grid = Grid()
        self.zoom: int = 32
        self.cam_offset = [0,0]
        self.dragging = False
        self.mouse_tile = (-1,-1)

        self.tick_speed = 10
        self.tick_timer = 0

        self.dir_index = 0
        self.sel_index = 0

        self.save_name = save_name

        self.resize()

    def get_mouse_tile(self):
        return [
            (mouse_pos[0]+self.cam_offset[0])//self.zoom, 
            (mouse_pos[1]+self.cam_offset[1])//self.zoom
        ]
    
    def resize(self):
        self.top_bar_rect =    pg.Rect(0,0,windowx,TOP_BAR_SIZE)
        self.bottom_bar_rect = pg.Rect(0,windowy-BOTTOM_BAR_SIZE,windowx,BOTTOM_BAR_SIZE)

    @property
    def direction(self):
        return directions[self.dir_index]

    @property
    def selected_block(self) -> Tile:
        return blocks[self.sel_index]

    def draw_tile(self, pos, color, direction=None, outline=0, roundness=0):
        rect = pg.Rect(
            pos[0]*self.zoom-self.cam_offset[0]+1,
            pos[1]*self.zoom-self.cam_offset[1]+1,
            self.zoom-2, self.zoom-2
        )
        if not rect.colliderect(pg.Rect(0,0,windowx,windowy)):
            return
        pg.draw.rect(screen, color, rect, outline, roundness)

        if direction != None:
            pg.draw.line(screen, (255,255,255),
                rect.center,
                [rect.centerx+direction[0]*(self.zoom/2-1), rect.centery+direction[1]*(self.zoom/2-1)]
            )


    def draw(self):
        roundness = int(self.zoom/6)

        # fading grid
        if self.mouse_in_bounds:
            top_x = self.mouse_tile[0]-GRID_FADE_IN_RADIUS+1
            top_y = self.mouse_tile[1]-GRID_FADE_IN_RADIUS+1

            for y in range(GRID_FADE_IN_RADIUS*2):
                y += top_y
                for x in range(GRID_FADE_IN_RADIUS*2):
                    x += top_x
                    distance = get_distance(*[i+0.5 for i in self.mouse_tile], x, y)
                    distance_key = GRID_FADE_IN_RADIUS-min(GRID_FADE_IN_RADIUS, distance)
                    distance_key /= GRID_FADE_IN_RADIUS
                    color = int(BG_BRIGHTNESS+(distance_key*DOT_BRIGHTNESS))
                    
                    pg.draw.circle(screen, (color,color,color), (
                        x*self.zoom-self.cam_offset[0],
                        y*self.zoom-self.cam_offset[1]
                    ), round(self.zoom/16))
        # objects
        for i in self.grid.tiles:
            self.draw_tile(i.pos, i.color if not i.powered else i.power_color, i.direction, roundness=roundness)
        # mouse tile
        if self.mouse_in_bounds:
            if self.hovered_block == None:
                self.draw_tile(self.mouse_tile, self.selected_block.color, self.direction, 3, roundness)
                self.draw_tile(self.mouse_tile, (128,128,128), self.direction, 1, roundness)
            else:
                self.draw_tile(self.mouse_tile, (255,255,255), self.direction, 1, roundness)

        # bars
        pg.draw.rect(screen, (30,30,30), self.top_bar_rect)
        pg.draw.rect(screen, (30,30,30), self.bottom_bar_rect)


    def update(self):
        # updating mouse
        self.mouse_in_bounds = mouse_pos[1] > TOP_BAR_SIZE\
            and mouse_pos[1] < windowy-BOTTOM_BAR_SIZE

        if mouse_wheel != 0 and self.mouse_in_bounds:
            # changing tick speed
            if keys[pg.K_LSHIFT]:
                self.tick_speed = max(min(self.tick_speed+mouse_wheel, fps), 1)

            # zooming
            elif keys[pg.K_LCTRL]:
                old_tile = [
                    (mouse_pos[0]+self.cam_offset[0])/self.zoom,
                    (mouse_pos[1]+self.cam_offset[1])/self.zoom
                ]
                self.zoom = max(min(self.zoom+mouse_wheel*2, 128), 4)
                difference = [
                    old_tile[0]*self.zoom-(mouse_pos[0]+self.cam_offset[0]),
                    old_tile[1]*self.zoom-(mouse_pos[1]+self.cam_offset[1])
                ]
                self.cam_offset[0] += difference[0]
                self.cam_offset[1] += difference[1]

            # changing direction
            else:
                self.dir_index = self.dir_index+mouse_wheel
                while self.dir_index < 0:
                    self.dir_index += len(directions)
                while self.dir_index >= len(directions):
                    self.dir_index -= len(directions)

        # moving camera
        if mmb_down and self.mouse_in_bounds:
            self.dragging = True
        elif not mouse_press[1]:
            self.dragging = False

        if self.dragging and mouse_moved != (0,0):
            self.cam_offset[0] -= mouse_moved[0]
            self.cam_offset[1] -= mouse_moved[1]

        # changing selected tile
        if num_pressed != None and num_pressed <= len(blocks):
            self.sel_index = int(num_pressed-1)

        # moving mouse
        self.prev_mouse_tile = type(self.mouse_tile)(self.mouse_tile)
        self.mouse_tile = self.get_mouse_tile()
        if self.mouse_tile != self.prev_mouse_tile:
            self.hovered_block = self.grid.find(self.mouse_tile)

        # pressing mouse
        if self.mouse_in_bounds:
            if mouse_press[0]:
                self.grid.place(self.selected_block, self.mouse_tile, self.direction)
            if mouse_press[2]:
                self.grid.erase(self.mouse_tile)

        # game tick
        self.tick_timer -= 1
        if self.tick_timer <= 0:
            self.tick_timer = self.tick_speed
            self.grid.tick()

        # copying map
        if pg.K_c in just_pressed and keys[pg.K_LCTRL]:
            clipboard.copy(save(self.grid))



# app variables

TOP_BAR_SIZE = 75
BOTTOM_BAR_SIZE = 20
GRID_FADE_IN_RADIUS = 6
BG_BRIGHTNESS = 20
DOT_BRIGHTNESS = 50

LEFT = [-1,0]
RIGHT = [1,0]
UP = [0,-1]
DOWN = [0,1]
LU = [-1,-1]
LD = [-1,1]
RU = [1,-1]
RD = [1,1]

directions = [
    UP,
    RU,
    RIGHT,
    RD,
    DOWN,
    LD,
    LEFT,
    LU
]
blocks = [
    Wire,
    Not,
    Splitter,
    Emitter,
    Threader,
]
dfps = 0.0


# app functions

def get_adjacent(dir, include_orig=True, dst=1):
    index = directions.index(dir)
    indexes = [index-dst, index, index+dst] if include_orig else [index-dst, index+dst]
    out = []
    for i in indexes:
        if i < 0: i += len(directions)
        if i > len(directions)-1: i -= len(directions)
        out.append(i)
    return [directions[i] for i in out]

def get_distance(x1, y1, x2, y2):
    return ((x1-x2)**2+(y1-y2)**2)**0.5

def save(grid: Grid) -> str:
    obj = []
    for i in grid.tiles:
        index = str(blocks.index(type(i)))
        obj.append(f'{index},{i.x},{i.y},{i.direction[0]},{i.direction[1]},{int(i.powered)}')
    return ';'.join(obj)

def load(save: str) -> Grid:
    obj = save.split(';')
    grid = Grid()
    for i in obj:
        args = [int(arg) for arg in i.split(',')]
        tile = blocks[args[0]](args[1], args[2], [args[3],args[4]])
        tile.powered = bool(args[5])
        grid.tiles.append(tile)
    return grid
    

# preparing

app = App()


# main loop

while running:
    # input
    events = pg.event.get()

    mouse_pos = pg.mouse.get_pos()
    mouse_press = pg.mouse.get_pressed(5)
    mouse_moved = pg.mouse.get_rel()
    mouse_wheel = 0

    keys = pg.key.get_pressed()
    just_pressed = []
    num_pressed = None

    lmb_down = False
    mmb_down = False

    screen.fill((BG_BRIGHTNESS, BG_BRIGHTNESS, BG_BRIGHTNESS))

    # events
    for event in events:
        if event.type == pg.QUIT:
            running = False 

        if event.type == pg.VIDEORESIZE:
            windowx = event.w
            windowy = event.h
            if windowx <= 640:
                windowx = 640
            if windowy <= 480:
                windowy = 480
            halfx = windowx//2
            halfy = windowy//2
            screen = pg.display.set_mode((windowx,windowy), pg.RESIZABLE)
            app.resize()

        if event.type == pg.MOUSEWHEEL:
            mouse_wheel = event.y

        if event.type == pg.KEYDOWN:
            just_pressed.append(event.key)
            if event.unicode.isdigit():
                num_pressed = int(event.unicode)

        if event.type == pg.MOUSEBUTTONDOWN:
            if event.button == pg.BUTTON_LEFT:
                lmb_down = True
            if event.button == pg.BUTTON_MIDDLE:
                mmb_down = True

    # updating
    app.update()
    app.draw()

    pg.display.flip()
    clock.tick(fps)
    dfps = round(clock.get_fps(), 2)