from manim import *

class SimpleNetwork(Scene):
    def construct(self):
        node1 = Dot(LEFT)
        node2 = Dot(RIGHT)
        edge = Arrow(start=LEFT, end=RIGHT, max_tip_length_to_length_ratio=0.1, buff=0.1)
        self.play(Create(node1), Create(node2))
        self.play(GrowArrow(edge))
        self.wait()