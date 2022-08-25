#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alex Hanson 12SDD01 Major AT3 - Platforming Game
27/06/2022
"""
import os, sys, json, pygame, ast, requests


def blurSurf(surface, amt=8):
    """
    Blur a pygame surface by scaling down then back up by a factor of amt.
    https://www.akeric.com/blog/?p=720
    """
    scale = 1.0 / float(amt)
    surf_size = surface.get_size()
    scale_size = (int(surf_size[0] * scale), int(surf_size[1] * scale))
    surf = pygame.transform.smoothscale(surface, scale_size)
    surf = pygame.transform.smoothscale(surf, surf_size)
    return surf


def make_objects(coinobjects=[], goalpos=[128, 780]):
    """
    Returns a sprite group of coin objects, and the goal object. Defined in map.json.
    """
    # print(coinobjects)
    coins = []
    for i in range(len(coinobjects)):
        # print(coinpos[i])
        coins.append(Object(coinobjects[i]))
    # print(coins)
    goal = [Object((goalpos[0], goalpos[1], 32, 32), "goal.png")]
    return pygame.sprite.Group(coins, goal)


class Player(pygame.sprite.Sprite):
    """
    Player Class containing collision, movement, and jumping.
    """

    def __init__(self, location, speed):
        """
        Setup all player variables and sprite.
        """
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.transform.scale(pygame.image.load("player.png").convert_alpha(), (50, 50))
        self.rect = self.image.get_rect(topleft=location)
        self.mask = pygame.mask.from_surface(self.image)
        self.jumppow = -9.0
        self.jumpcutpow = -4
        self.jumpbuffer = 0
        self.speed = speed
        self.x_vel, self.y_vel = 0, 0
        self.gravity = 0.25
        self.inair = False
        self.accel = 0
        self.minicollectibles = 0
        self.collbellow = False

    def checkInput(self, keys):
        """
        Check the player's input and update the player's velocity.
        """
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.accel = -1
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.accel = 1
        else:
            self.accel = 0
        """
        Acceleration from https://stackoverflow.com/a/49759249/13227148 by "skrx"
        """
        self.x_vel += self.accel  # Accelerate.
        if abs(self.x_vel) >= self.speed:  # If max_speed is exceeded.
            # Normalize the x_change and multiply it with the max_speed.
            self.x_vel = self.x_vel / abs(self.x_vel) * self.speed
        if not self.accel:
            self.x_vel = round(self.x_vel * 0.9, 3)

    def checkPos(self, objects, mask, gameClassRef):
        """
        Get the player's position and check for collisions.
        """
        if not self.inair:
            # Check if the player is falling and reset vars.
            if self.collbellow is None:
                self.inair = True
            self.y_vel = 0
            self.jumpbuffer = 0
        else:
            # calculate gravity, vertical collision, and jump buffer
            y_change = self.check_collisions(self.y_vel, mask, 1)
            self.rect.move_ip((0, y_change[0]))
            self.inair = y_change[1]
            self.jumpbuffer += 1
        if self.x_vel:
            # Check horizontal collision and move player.
            x_change = self.check_collisions(self.x_vel, mask, 0)
            self.rect.move_ip((x_change[0], 0))
        # test sprite collision for objects
        for obj in objects:
            if pygame.sprite.collide_mask(self, obj):
                # collided with a sprite
                if obj.rect.topleft == (gameClassRef.currentgoalpos[0], gameClassRef.currentgoalpos[1]):
                    # collided with goal
                    gameClass.win(gameClassRef)
                else:
                    # collided with a collectible
                    self.minicollectibles += 1
                # remove the sprite
                objects.remove(obj)

    def check_collisions(self, offset, mask, index):
        """
        Check collision against a level mask (alpha channel of level image)
        when moving the player by the desired offset; The loop will attempt
        to find the furthest distance the player may move without colliding.
        """
        test_offset = list(self.rect.topleft)
        test_offset[index] += offset
        notmoved = True
        itr = 0
        while mask.overlap_area(self.mask, test_offset):
            self.rect.move_ip(0, -1)
            offset -= (-1 if offset < 0 else 1)
            test_offset = list(self.rect.topleft)
            test_offset[index] += offset
            notmoved = False
            itr += 1
            if itr > 100:
                # infinite loop detected
                break
        self.rect.move_ip(0, 1)
        # bounce on high impact
        if not notmoved and self.y_vel >= 1 and self.inair and self.isOnGround(mask, self.y_vel):
            # print(index)
            if not index:
                self.y_vel = 0
                self.inair = False
                return offset, False
            self.y_vel *= -0.6
            self.inair = True
            notmoved = True
        return offset, notmoved

    def isOnGround(self, mask, checkdistance=1):
        """Check to see if the player is contacting the ground."""
        self.rect.move_ip((0, checkdistance))
        result = mask.overlap(self.mask, self.rect.topleft)
        self.rect.move_ip((0, -checkdistance))
        return result

    def roomAbove(self, mask):
        """
        Check if there is room above the player to jump
        """
        self.rect.move_ip(0, -1)
        result = mask.overlap(self.mask, self.rect.topleft)
        self.rect.move_ip(0, 1)
        return result

    def jump(self, mask):
        """
        Apply vertical velocity if the player is on the ground.
        """
        # give the player a 15 frame jump buffer if they become airborne and miss a jump
        if not self.inair and not self.roomAbove(mask) or self.jumpbuffer < 15:
            self.y_vel = self.jumppow
            self.inair = True

    def releaseJump(self):
        """
        Prematurely stop the player's jump upon release of the jump button
        """
        if self.inair:
            if self.y_vel < self.jumpcutpow:
                self.y_vel = self.jumpcutpow

    def gravityTick(self):
        """
        Apply gravity if airborne
        """
        if self.inair:
            self.y_vel += self.gravity
        else:
            self.y_vel = 0

    def update(self, objects, keys, mask, gameClassRef):
        """
        Update the player's position and check for collisions.
        """
        self.collbellow = self.isOnGround(mask)
        self.checkInput(keys)
        self.checkPos(objects, mask, gameClassRef)
        self.gravityTick()

    def draw(self, surface):
        """
        Draw the player to the screen.
        """
        surface.blit(self.image, self.rect)


class Object(pygame.sprite.Sprite):
    """
    Collectible object class for both coins and the main goal.
    """

    def __init__(self, rect, img="coin.png"):
        pygame.sprite.Sprite.__init__(self)
        self.rect = pygame.Rect(rect)
        self.image = pygame.image.load(img).convert_alpha()


class gameClass(object):
    """
    Class for the entire game loop and logic.
    """

    def __init__(self, width=2048, height=1024, player_start=[50, 600], speed=4, level=r"1.png", coinobjs=[],
                 goalpos=[], mapindex=2):
        """Initialise variables"""
        self.screen = pygame.display.get_surface()
        self.screen_rect = self.screen.get_rect()
        self.clock = pygame.time.Clock()
        self.fps = 60
        self.keys = pygame.key.get_pressed()
        self.gamequit = False
        self.player = Player((player_start[0], player_start[1]), speed)
        self.viewport = self.screen.get_rect()
        self.level = pygame.Surface((width, height)).convert()
        self.level_rect = self.level.get_rect()
        self.objects = make_objects(coinobjs, goalpos)
        self.currentgoalpos = goalpos
        self.currentmapindex = mapindex
        self.mapdir = os.path.join(os.getcwd(), r'maps')
        self.image = pygame.image.load(os.path.join(self.mapdir, level)).convert_alpha()
        self.mask = pygame.mask.from_surface(self.image)
        self.paused = False
        self.canunpause = False
        self.won = False

    def event_loop(self):
        """We can always quit, and the player can sometimes jump."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT or self.keys[pygame.K_ESCAPE]:
                self.gamequit = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE or event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.player.jump(self.mask)
                if event.key == pygame.K_p:
                    self.canunpause = False
                    if self.paused and not self.canunpause:
                        self.paused = False
                    else:
                        self.paused = True
                    if self.won:
                        self.gamequit = True
                        # intentionally crash to close the game
                        map_name = maplist[self.currentmapindex-1]
                        with open(os.path.join(directory, map_name), 'r') as f:
                            map_info = json.loads(f.read())
                        game = gameClass(map_info["width"], map_info["height"], map_info["player_start"],
                                         map_info["speed"],
                                         map_info["level"], ast.literal_eval(map_info["coinobjs"]), map_info["goalpos"])
                        game.main()
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE or event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.player.releaseJump()
                if event.key == pygame.K_p:
                    self.canunpause = True
            if event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode(event.dict['size'],
                                                      flags=pygame.DOUBLEBUF | pygame.SCALED | pygame.HWSURFACE,
                                                      vsync=1)
                self.screen_rect = self.screen.get_rect()
                self.viewport = self.screen.get_rect()
                self.viewport.center = self.player.rect.center
                self.viewport.clamp_ip(self.level_rect)
                # self.viewport.clamp_ip(self.rect)

    def update(self):
        """
        Update keypresses, tick player position, and viewport.
        """
        self.keys = pygame.key.get_pressed()
        self.objects.update(self.player, self.objects)
        self.player.update(self.objects, self.keys, self.mask, self)
        self.viewport.center = self.player.rect.center
        self.viewport.clamp_ip(self.level_rect)

    def win(self):
        """
        Events to run when player reaches the goal.
        """
        self.paused = True
        self.won = True

    def draw(self):
        """
        Draw to the level, then draw the viewport of the level to the screen
        """
        # background
        self.level.fill(pygame.Color("lightblue"))
        self.objects.draw(self.level)
        self.player.draw(self.level)
        self.screen.blit(self.level, (0, 0), self.viewport)
        self.screen.blit(self.image, (0, 0), self.viewport)
        # pause screen
        if self.paused:
            self.screen.blit(blurSurf(self.screen), (0, 0))
            font = pygame.font.SysFont('Berlin Sans FB', 64)
            if self.won:
                textsurface = font.render("You reached the goal!", False, pygame.color.Color('black'))
            else:
                textsurface = font.render("Paused", False, pygame.color.Color('black'))
            self.screen.blit(textsurface, (
                screensize[0] / 2 - textsurface.get_width() / 2, screensize[1] / 3 - textsurface.get_height()))
            font = pygame.font.SysFont('Berlin Sans FB', 18)
            if self.won:
                textsurface = font.render("Press P to play the next level", False, pygame.Color(67, 67, 67))
            else:
                textsurface = font.render("Press P again to unpause", False, pygame.Color(67, 67, 67))
            self.screen.blit(textsurface, (
                screensize[0] / 2 - textsurface.get_width() / 2, screensize[1] / 3 - textsurface.get_height() / 4))

    def getFPS(self):
        """
        Update window title with FPS
        """
        caption = f"{windowtitle} - FPS: {round(self.clock.get_fps(), 2)}"
        pygame.display.set_caption(caption)

    def main(self):
        """game loop"""
        while not self.gamequit:
            self.event_loop()
            if not self.paused:
                self.update()
            self.draw()
            pygame.display.update()
            # update fps after draw
            self.clock.tick(self.fps)
            self.getFPS()


if __name__ == "__main__":
    # centre the screen https://stackoverflow.com/questions/38703791/how-do-i-place-the-pygame-screen-in-the-middle
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pygame.init()
    windowtitle = "Platformer - AH 12SDD01"
    screensize = (860, 480)
    pygame.display.set_caption(windowtitle)
    maplist = []
    mapindex = 2
    directory = os.path.join(os.getcwd(), r'maps')
    # automatically fetch new maps to grab new maps without updating the game

    try:
        # try retrieve the map list from json
        map_infoweb = requests.get('https://raw.githubusercontent.com/dippyshere/fluffy-computing-machine/main'
                                   '/maplist.json')
        map_infowebj = json.loads(map_infoweb.text)
        # for each map in the list, download its image and data
        for i in range(0,int(map_infowebj['num'])):
            # https://stackoverflow.com/a/37821542/13227148 (Vlad Bezden)
            img_data = requests.get(map_infowebj['url'+str(i+1)+'img']).content
            with open(os.path.join(directory, map_infowebj['name'+str(i+1)+'img']),'wb') as handler:
                handler.write(img_data)
                print("Downloaded map: " + map_infowebj['name'+str(i+1)+'img'])
            map_json = json.loads(requests.get(map_infowebj['url'+str(i+1)+'data']).text)
            with open(os.path.join(directory, map_infowebj['name'+str(i+1)+'data']), 'w') as f:
                json.dump(map_json,f)
                print("Downloaded map data: " + map_infowebj['url'+str(i+1)+'data'])
    except Exception as e:
        print(e)
    # after downloading, build a list of maps
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            maplist.append(filename)
        else:
            continue
    # load map from json info
    map_name = maplist[mapindex]
    with open(os.path.join(directory, map_name), 'r') as f:
        map_info = json.loads(f.read())
    # vsync display + scale to max size
    flags = pygame.DOUBLEBUF | pygame.SCALED | pygame.HWSURFACE
    pygame.display.set_mode(screensize, flags, vsync=1)
    game = gameClass(map_info["width"], map_info["height"], map_info["player_start"], map_info["speed"],
                       map_info["level"], ast.literal_eval(map_info["coinobjs"]), map_info["goalpos"], mapindex)
    game.main()
    pygame.quit()
    sys.exit()
