import pymunk
from pymunk.vec2d import Vec2d
from pyglet.sprite import Sprite

from .game_object import GameObject


class Actor(GameObject, Sprite):
    def __init__(self, body: pymunk.Body, shape: pymunk.Shape, *args, pos, **kwargs):
        pos = Vec2d(pos)
        super().__init__(*args, x=pos.x, y=pos.y, **kwargs)

        self.body = body
        self.shape = shape

    def tick(self, dt: float):
        self.x = self.body.position.x
        self.y = self.body.position.y