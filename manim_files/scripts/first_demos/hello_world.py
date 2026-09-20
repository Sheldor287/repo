from manim import *

class HelloManim(Scene):
    def construct(self):
        circle = Circle().shift(LEFT)
        square = Square().shift(RIGHT)

        self.play(Create(circle))
        self.play(Create(square))

        self.wait()

