import random
from typing import Optional

from pymunk.vec2d import Vec2d
import pymunk
import pytweening

from . import Actor, resources, CollisionType, WIDTH, HEIGHT, make_color, valmap


class Enemy(Actor):
    """Base class for all the enemies"""
    SIZE = Vec2d(0, 0)

    def __init__(self, *, mass, size, img, pos, player, collision_type, batch=None, **kwargs):
        # Make a body and shape from the mass and size
        body = pymunk.Body(mass, pymunk.moment_for_box(mass, size))
        # Make sure to add a tiny radius to the box poly to make collision more efficient
        shape = pymunk.Poly.create_box(body, size, 1)
        # Assign correct collision type
        shape.collision_type = collision_type
        shape.filter = pymunk.ShapeFilter(categories=collision_type,
                                          mask=pymunk.ShapeFilter.ALL_MASKS ^ CollisionType.WallSensor ^ CollisionType.WallKill)
        # Initialize actor with our body and shape
        super().__init__(body=body, shape=shape, img=img, batch=batch, pos=pos, **kwargs)

        # Hold on to some values we need
        self.player = player
        self.size = Vec2d(size)


class EnemyPawn(Enemy):
    """A small enemy that simply follows the player."""
    SIZE = Vec2d(32, 32)

    def __init__(self, *, pos, player, batch=None, **kwargs):
        super().__init__(mass=10, size=self.SIZE, img=resources.enemy_pawn_image, pos=pos, player=player,
                         collision_type=CollisionType.EnemyPawn, batch=batch, **kwargs)
        self.speed = 10

    def tick(self, dt: float):
        super().tick(dt)

        # Find vector to player and set it as our velocity (accounting for speed)
        vel = Vec2d(self.player.position) - Vec2d(self.position)
        self.body.velocity = vel.normalized() * self.speed


class EnemySlider(Enemy):
    """A big and fast enemy that slides towards the player, but only moves in a single cardinal direction at once."""
    SIZE = Vec2d(128, 128)

    def __init__(self, *, pos, player, batch=None, **kwargs):
        super().__init__(mass=500, size=self.SIZE, img=resources.enemy_slider_image, pos=pos, player=player,
                         collision_type=CollisionType.EnemySlider, batch=batch, **kwargs)

        # Start out in a pleasant screen color (will only tint the white part of the sprite)
        self.color = make_color(hue=110 / 360, saturation=1, luminance=0.5)

        self.speed = 100

        self.wait_timer = 0
        self.moving = False
        self.start_pos: Optional[Vec2d] = None
        self.end_pos: Optional[Vec2d] = None
        self.move_timer = 0

        # if the x axis is preferred to get close the player
        self.x_axis_preferred = bool(random.getrandbits(1))

    @staticmethod
    def init_collision(game_window):
        """Setup collision for EnemySlider.

        Will ignore collisions between EnemySlider and Wall.
        Will also override collision for EnemySlider and Player.
        """

        def push(arbiter, slider, pushee):
            # Get unit vector of how the EnemySlider is moving currently
            direction = (slider.end_pos - slider.start_pos).normalized()
            # Get how far the player and EnemySlider is from each other
            distance = abs(arbiter.contact_point_set.points[0].distance)
            # Then simply push the player in that direction
            pushee.body.position += direction * distance
            # Ignore default collision response

        def player_collision_pre_solve(arbiter, space, data):
            # Find what is essentially *self* by looking at the owner of the EnemySlider shape that collided
            slider = arbiter.shapes[1].owner
            push(arbiter, slider, arbiter.shapes[0])
            return False

        def pellet_collision_pre_solve(arbiter, space, data):
            # Find what is essentially *self* by looking at the owner of the EnemySlider shape that collided
            slider = arbiter.shapes[1].owner
            return (slider.end_pos - slider.pos).length < 128

        # Override player collision
        # We need this because standard pymunk collision likes to just push the player to the side
        # We want the player to be pushed in exactly the same direction as the EnemySlider is moving
        collision = game_window.space.add_collision_handler(CollisionType.Player, CollisionType.EnemySlider)
        collision.pre_solve = player_collision_pre_solve

        # Push pellets if they would otherwise have been inside us
        collision = game_window.space.add_collision_handler(CollisionType.Pellet, CollisionType.EnemySlider)
        collision.pre_solve = pellet_collision_pre_solve

    def tick(self, dt: float):
        super().tick(dt)

        self.wait_timer += dt

        # As long as we're not moving we want to calculate where we would like to move in the future
        # This is so we can rotate the sprite
        if not self.moving:
            # Adjust color to be more red the closer wait_timer gets to 0
            self.color = make_color(hue=valmap(self.wait_timer, 3, 0, 0, 110) / 360, saturation=1, luminance=0.5)

            # If we're not moving and we've been waiting for 3 sec
            if self.wait_timer > 3:
                # Then move
                self.moving = True
                self.move_timer = 0

            # Clear some vectors
            self.end_pos = Vec2d()
            self.start_pos = self.pos
            # Find delta vector to player
            delta = self.player.pos - self.pos

            # If we are able to hit the player by moving vertically
            if -64 < delta.y < 64:
                # Don't move in y dir
                self.end_pos.y = self.pos.y
                # Move to the edge of the screen in the x dir (either left or right)
                if delta.x > 0:
                    self.end_pos.x = WIDTH - self.size.x / 2
                else:
                    self.end_pos.x = self.size.x / 2
            # If we are able to hit the player by moving horizontally
            elif -64 < delta.x < 64:
                # Don't move in x dir
                self.end_pos.x = self.pos.x
                # Move to the edge of the screen in the y dir (either top or bottom)
                if delta.y > 0:
                    self.end_pos.y = HEIGHT - self.size.y / 2
                else:
                    self.end_pos.y = self.size.y / 2
            # If we are not able to hit the player
            else:
                # Try to get in line with the player
                if self.x_axis_preferred:
                    self.end_pos.y = self.pos.y
                    self.end_pos.x = self.player.x
                else:
                    self.end_pos.x = self.pos.x
                    self.end_pos.y = self.player.y

            # Rotate so we face the direction we want to move
            # The 270 - angle is due to how the sprite is facing
            self.rotation = 270 - (self.start_pos - self.end_pos).angle_degrees

        # If we are currently moving
        if self.moving:
            # Increase the move timer by a small bit taking into account how long we need to move and at what speed
            # The 5 is simply a multiplier to make the speed feel approx equal to other speeds in the game
            self.move_timer += dt * (5 / (self.end_pos.get_distance(self.start_pos) / self.speed))
            # Change the position of the body according to a bounding algorithm
            self.body.position = self.start_pos + (self.end_pos - self.start_pos) * pytweening.easeOutBounce(
                min(self.move_timer, 1))
            # Then if we're done moving
            if self.move_timer >= 1.0:
                self.wait_timer = 0
                self.moving = False
                # Maybe choose another preferred axis
                self.x_axis_preferred = bool(random.getrandbits(1))
        else:
            # Reset velocity so if we got pushed we stop
            self.body.velocity = (0, 0)
