import tdl
from random import randint
import colors
import math
import textwrap

# Size of the Window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# Size of the Map
MAP_WIDTH = 80
MAP_HEIGHT = 43

# Parameters for Dungeon Generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3

# Parameters for Realtime Capability
REALTIME = False
LIMIT_FPS = 20

# default Field of View algorithm
FOV_ALGO = 'BASIC'
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

# Message bar constants
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
#create the list of game messages and their colors, starts empty
game_msgs = []

# RGB Color Codes
color_dark_wall = (0, 0, 100)
color_light_wall = (130, 110, 50)
color_dark_ground = (50, 50, 150)
color_light_ground = (200, 180, 50)

# set default states
fov_recompute = True
game_state = 'playing'
player_action = None


#############################################
#              C L A S S E S                #
#############################################

class Tile:
    # a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        self.explored = False
 
        # If a tile is blocked, it also blocks sight
        if block_sight is None: 
            block_sight = blocked
        self.block_sight = block_sight

class Rect:
    # a rectangle to characterize a Room on the map.
    def __init__(self, x, y, w, h):
        # x/y coordinates of point of origin 
        self.x1 = x
        self.y1 = y
        # x/y coordinates of endpoint (adds width and height)
        self.x2 = x + w
        self.y2 = y + h
    
    def center(self):
        # calculates coordinates of room center
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2
        return (center_x, center_y)
 
    def intersect(self, other):
        # returns True if rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

class GameObject:
    # generic object: the player, a monster, an item, the stairs...
    # always represented by a character on screen.
    def __init__(self, x, y, char, name, color, blocks=False, 
                 fighter=None, ai=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.fighter = fighter
        self.ai = ai
        
        if self.fighter:  # let the fighter component know who owns it
            self.fighter.owner = self
        
        if self.ai:  # let the AI component know who owns it
            self.ai.owner = self
        
    def send_to_back(self):
        # make this object be drawn first, so all others appear above it if they're in the same tile.
        global objects
        objects.remove(self)
        objects.insert(0, self)
 
    def move(self, dx, dy):
        # Move by the given amount if destination not blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        # vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)
 
        # normalize it to length 1 (preserving direction), then round
        # convert to integer so the movement is restricted to the grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)
    
    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)
 
    def draw(self):
        global visible_tiles
        
        # only show if it's visible to the player
        if (self.x, self.y) in visible_tiles:
            # draw the character at its position
            con.draw_char(self.x, self.y, self.char, self.color, bg=None)
 
    def clear(self):
        # erase the character
        con.draw_char(self.x, self.y, ' ', self.color, bg=None)

class Fighter:
    # combat-related properties and methods (monster, player, NPC).
    def __init__(self, hp, defense, power, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function
    
    def take_damage(self, damage):
        # apply damage if possible
        if damage > 0:
            self.hp -= damage

            # check for death. if there's a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)
    
    def attack(self, target):
        #a simple formula for attack damage
        damage = self.power - target.fighter.defense
 
        if damage > 0:
            # make the target take some damage
            message((self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.'), colors.peach)
            target.fighter.take_damage(damage)
        else:
            message((self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!'),colors.peach)

class BasicMonster:
    # AI for a basic monster.
    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it can see you
        monster = self.owner
        if (monster.x, monster.y) in visible_tiles:
 
            # move towards player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
 
            # close enough, attack! (if the player is still alive.)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

#############################################
#            F U N C T I O N S              #
#############################################

def create_room(room):
    global my_map
    # go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            my_map[x][y].blocked = False
            my_map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
    global my_map
    # go through the tiles in the tunnel and make them passable
    for x in range(min(x1, x2), max(x1, x2) + 1):
        my_map[x][y].blocked = False
        my_map[x][y].block_sight = False
 
def create_v_tunnel(y1, y2, x):
    global my_map
    # go through the tiles in the tunnel and make them passable
    for y in range(min(y1, y2), max(y1, y2) + 1):
        my_map[x][y].blocked = False
        my_map[x][y].block_sight = False

def is_visible_tile(x, y):
    global my_map
 
    if x >= MAP_WIDTH or x < 0:
        return False
    elif y >= MAP_HEIGHT or y < 0:
        return False
    elif my_map[x][y].blocked == True:
        return False
    elif my_map[x][y].block_sight == True:
        return False
    else:
        return True

def is_blocked(x, y):
    # first test the map tile
    if my_map[x][y].blocked:
        return True
 
    # now check for any blocking objects
    for obj in objects:
        if obj.blocks and obj.x == x and obj.y == y:
            return True
 
    return False

def place_objects(room):
    # choose random number of monsters
    num_monsters = randint(0, MAX_ROOM_MONSTERS)
    
    for i in range(num_monsters):
        # choose random spot for this monster
        x = randint(room.x1, room.x2)
        y = randint(room.y1, room.y2)

        if not is_blocked(x, y):
            # 80% chance of getting an orc
            if randint(0, 100) < 80:  #80% chance of getting an orc
                # create an orc
                fighter_component = Fighter(hp=10, defense=0, power=2,
                                            death_function=monster_death)
                ai_component = BasicMonster()
                
                monster = GameObject(x, y, 'o', 'orc', colors.desaturated_green,
                    blocks=True, fighter=fighter_component, ai=ai_component,)
            
            else:
                # create a troll
                fighter_component = Fighter(hp=14, defense=1, power=3)
                ai_component = BasicMonster()

                monster = GameObject(x, y, 'T', 'troll', colors.darker_green,
                    blocks=True, fighter=fighter_component, ai=ai_component)
    
            objects.append(monster)

def make_map():
    global my_map
 
    # fill map with "blocked" tiles
    my_map = [[ Tile(True)
        for y in range(MAP_HEIGHT) ]
            for x in range(MAP_WIDTH) ]
    
    rooms = []
    num_rooms = 0
 
    for r in range(MAX_ROOMS):
        
        # set random width and height
        w = randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        # set random position within map
        x = randint(0, MAP_WIDTH-w-1)
        y = randint(0, MAP_HEIGHT-h-1)

        # create room with "Rect" class
        new_room = Rect(x, y, w, h)
 
        # check for overlap with previously created rooms
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            # if no intersection, create Room
            create_room(new_room)

            # set center coordinates of new room
            (new_x, new_y) = new_room.center()

            if num_rooms == 0:
                # if first room, set player position to center
                player.x = new_x
                player.y = new_y

            else:
                # for all other rooms, connect to previous with tunnel

                # set center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms-1].center()

                # flip a coin
                if randint(0, 1):
                    #first move horizontally, then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #first move vertically, then horizontally
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)
    
            # add some contents to this room, such as monsters
            place_objects(new_room)

            # append the new room to the list of rooms
            rooms.append(new_room)
            num_rooms += 1

def render_all():
    global fov_recompute
    global visible_tiles
 
    if fov_recompute:
        fov_recompute = False
        visible_tiles = tdl.map.quickFOV(player.x, player.y,
                                         is_visible_tile,
                                         fov=FOV_ALGO,
                                         radius=TORCH_RADIUS,
                                         lightWalls=FOV_LIGHT_WALLS)
                                         
        # go through all tiles and set background color according to FOV   
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = (x, y) in visible_tiles
                wall = my_map[x][y].block_sight
                if not visible:
                    # if it's not visible right now, 
                    # the player can only see it if it's explored
                    if my_map[x][y].explored:
                        # it's out of the player's FOV
                        if wall:
                            con.draw_char(x, y, None, fg=None, bg=color_dark_wall)
                        else:
                            con.draw_char(x, y, None, fg=None, bg=color_dark_ground)
                else:
                    if wall:
                        con.draw_char(x, y, None, fg=None, bg=color_light_wall)
                    else:
                        con.draw_char(x, y, None, fg=None, bg=color_light_ground)
                    # since it's visible, explore it
                    my_map[x][y].explored = True

    # draw all the objects in the list
    for obj in objects:
        if obj != player:
            obj.draw()
    player.draw()

    # 'blit' the contents of the new console to the root, to display them
    root.blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0)

    # prepare to render the GUI panel
    panel.clear(fg=colors.white, bg=colors.black)

    #print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        panel.draw_str(MSG_X, y, line, bg=None, fg=color)
        y += 1
 
    #show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
        colors.light_red, colors.darker_red)
 
    #blit the contents of "panel" to the root console
    root.blit(panel, 0, PANEL_Y, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0)

def player_move_or_attack(dx, dy):
    global fov_recompute
 
    # the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy
 
    #try to find an attackable object there
    target = None
    for obj in objects:
        if obj.fighter and obj.x == x and obj.y == y:
            target = obj
            break
 
    # attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

def player_death(player):
    # the game ended!
    global game_state
    message('You died!',colors.red)
    game_state = 'dead'
 
    # for added effect, transform the player into a corpse!
    player.char = '%'
    player.color = colors.dark_red
 
def monster_death(monster):
    # transform it into a nasty corpse! 
    # it doesn't block, can't be attacked and doesn't move
    message((monster.name.capitalize() + ' is dead!'),colors.red)
    monster.char = '%'
    monster.color = colors.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()

def handle_keys():
    global playerx, playery 
    global fov_recompute

    if REALTIME:
        keypress = False
        for event in tdl.event.get():
            if event.type == 'KEYDOWN':
               user_input = event
               keypress = True
        if not keypress:
            return
 
    # Use turn-based if no "realtime"
    else: 
        user_input = tdl.event.key_wait()
 
    # ALT + Enter: toggle fullscreen
    if user_input.key == 'ENTER' and user_input.alt:
        tdl.set_fullscreen(True)
    
    # ESC: exit game
    elif user_input.key == 'ESCAPE':
        return 'exit'   
    
    if game_state == 'playing':
        # Movement keys
        if user_input.key == 'UP':
            player_move_or_attack(0, -1)
    
        elif user_input.key == 'DOWN':
            player_move_or_attack(0, 1)
    
        elif user_input.key == 'LEFT':
            player_move_or_attack(-1, 0)
    
        elif user_input.key == 'RIGHT':
            player_move_or_attack(1, 0)
        
        else:
            return 'didnt-take-turn'

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #render a bar (HP, experience, etc). first calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)
 
    #render the background first
    panel.draw_rect(x, y, total_width, 1, None, bg=back_color)
 
    #now render the bar on top
    if bar_width > 0:
        panel.draw_rect(x, y, bar_width, 1, None, bg=bar_color)
    
    #finally, some centered text with the values
    text = name + ': ' + str(value) + '/' + str(maximum)
    x_centered = x + (total_width-len(text))//2
    panel.draw_str(x_centered, y, text, fg=colors.white, bg=None)

def message(new_msg, color = colors.white):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
 
    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
 
        #add the new line as a tuple, with the text and the color
        game_msgs.append((line, color))
    

#############################################
#        Initialization & Main Loop         #
#############################################


tdl.set_font('arial10x10.png', greyscale=True, altLayout=True)
root = tdl.init(SCREEN_WIDTH, SCREEN_HEIGHT, title="Roguelike", fullscreen=False)
con = tdl.Console(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = tdl.Console(SCREEN_WIDTH, PANEL_HEIGHT)

tdl.setFPS(LIMIT_FPS)

# create object representing the player
fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
player = GameObject(0, 0, '@', 'player', colors.white, blocks=True, fighter=fighter_component)
 
# the list of objects starting with the player
objects = [player]

make_map()

#a warm welcoming message!
message('W E L C O M E ! Prepare to perish in the Tombs of the Ancient Kings.', colors.dark_flame)

while not tdl.event.is_window_closed():
    
    # draw all objects in the list
    render_all()
    tdl.flush()

    # erase all objects in their old locations before they move
    for obj in objects:
        obj.clear()

    # handle keys and exit game if needed
    player_action = handle_keys()
    if player_action == 'exit':
        break
    
    #let monsters take their turn
    if game_state == 'playing' and player_action != 'didnt-take-turn':
        for obj in objects:
            if obj.ai:
                obj.ai.take_turn()