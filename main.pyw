############## INITIALIZATION ##############

import pygame as pg
import easing_functions as easing
import copy
import draw
from typing import List

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
        self.pos = [x, y]
        self.color = (64,0,0)
        self.power_color = (255,0,0)
        self.name = ''
        self.description = ''

    @property
    def x(self):
        return self.pos[0]

    @property
    def y(self):
        return self.pos[1]
    
    def can_power(self, offset):
        if not self.powered: return False
        if offset != self.direction: return False
        return True

    def can_be_powered(self, offset):
        return True
    

class Wire(Tile):
    name = 'Wire'
    description = 'Transfers signal from its back to its front.'

    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)

class Splitter(Tile):
    name = 'Splitter'
    description = 'Transfers signal from its back to everywhere except its back and tiles adjacent to its back.'

    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
        self.color = (90,30,30)
        self.power_color = (255,80,80)
    
    def can_power(self, offset):
        if not self.powered: return False
        if self.direction in get_adjacent([-offset[0], -offset[1]]):
            return False
        return True
    
class Emitter(Tile):
    name = 'Emitter'
    description = 'Emits constant signal from its front. Cannot be turned off.'
    
    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
        self.powered = True
        self.color = (255,128,128)
        self.power_color = (255,128,128)

    def can_be_powered(self, offset):
        return False
    
    def can_power(self, offset):
        if offset != self.direction: return False
        return True
    
class Threader(Tile):
    name = 'Threader'
    description = 'Splits the incoming signal to the sides adjacent to its front.'
    
    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
        self.powered = False
        self.color = (0,32,128)
        self.power_color = (0,64,255)
    
    def can_power(self, offset):
        if not self.powered: return False
        if self.direction in get_adjacent(offset, False):
            return True
        return False
    
class Not(Tile):
    name = 'Not Gate'
    description = 'Emits a signal from its front if it doesn\'t receive power from its back.'

    def __init__(self, x, y, dir):
        super().__init__(x, y, dir)
        self.color = (64,64,64)
        self.power_color = (192,192,192)
    
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
                offset = [intpos[0]-i.pos[0], intpos[1]-i.pos[1]]
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
    def __init__(self, save_name):
        self.grid: Grid = Grid()
        self.zoom: int = 32
        self.cam_offset = [0,0]

        self.tick_speed = 10
        self.tick_timer = 0

        self.dir_index = 0
        self.sel_index = 0

        self.save_name = save_name

    def get_mouse_tile(self):
        return [
            (mouse_pos[0]+self.cam_offset[0])//self.zoom, 
            (mouse_pos[1]+self.cam_offset[1])//self.zoom
        ]

    @property
    def direction(self):
        return directions[self.dir_index]

    @property
    def selected_block(self) -> Tile:
        return blocks[self.sel_index]

    def draw_tile(self, pos, color, direction=None, outline=0):
        rect = pg.Rect(
            pos[0]*self.zoom-self.cam_offset[0],
            pos[1]*self.zoom-self.cam_offset[1],
            self.zoom, self.zoom
        )
        if not rect.colliderect(pg.Rect(0,0,windowx,windowy)):
            return
        pg.draw.rect(screen, color, rect, outline)

        if direction != None:
            pg.draw.line(screen, (255,255,255),
                rect.center,
                [rect.centerx+direction[0]*(self.zoom/2-1), rect.centery+direction[1]*(self.zoom/2-1)]
            )


    def draw(self):
        # grid
        for i in self.grid.tiles:
            self.draw_tile(i.pos, i.color if not i.powered else i.power_color, i.direction)
        self.draw_tile(self.mouse_tile, (255,255,255), self.direction, 1)

        draw.text(f'{self.sel_index}, {self.selected_block.name}')

    def update(self):
        if mouse_wheel != 0:
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

        # changing selected tile
        if num_pressed != None and num_pressed <= len(blocks):
            self.sel_index = int(num_pressed-1)

        # moving camera
        if mouse_press[1] and mouse_moved != (0,0):
            self.cam_offset[0] -= mouse_moved[0]
            self.cam_offset[1] -= mouse_moved[1]

        # moving mouse
        self.mouse_tile = self.get_mouse_tile()

        # pressing mouse
        if mouse_press[0]:
            self.grid.place(self.selected_block, self.mouse_tile, self.direction)
        if mouse_press[2]:
            self.grid.erase(self.mouse_tile)

        # game tick
        self.tick_timer -= 1
        if self.tick_timer <= 0:
            self.tick_timer = self.tick_speed
            self.grid.tick()



# app variables

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

def save(grid: Grid) -> str:
    obj = []
    for i in grid.tiles:
        index = str(blocks.index(type(i)))
        obj.append(f'{index},{i.x},{i.y},{i.dir[0]},{i.dir[1]},{int(i.powered)}')
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

app = App('new')


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

    screen.fill((0,0,0))

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

        if event.type == pg.MOUSEWHEEL:
            mouse_wheel = event.y

        if event.type == pg.KEYDOWN:
            just_pressed.append(event.key)
            if event.unicode.isdigit():
                num_pressed = int(event.unicode)

    # updating
    app.update()
    app.draw()

    pg.display.flip()
    clock.tick(fps)