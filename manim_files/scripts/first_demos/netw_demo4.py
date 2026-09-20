from manim import *

class Demo(Scene):

    def construct(self):

        arrow_kwargs = {'tip_length': 0.15, 'max_tip_length_to_length_ratio': 1.0, 'buff': 0.33,}

        # Node positions
        nodes, edges = {}, {}
        pos = {0: LEFT * 2, 1: UP * 1.5, 2: RIGHT * 1.5, 3: DOWN * 1.5, 4: RIGHT * 2.5 + DOWN * 1.5,}
        edge_list = [(0,1), (0,2), (0,3), (1,2), (2,4), (3,4),]

        # Create nodes
        for i, val in pos.items():
            nodes[i] = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
            nodes[i].move_to(val)

        # Create edges
        for u, v in edge_list:
            edges[(u,v)] = Arrow(nodes[u].get_center(), nodes[v].get_center(), **arrow_kwargs)

        # Groups
        node_group = VGroup(*nodes.values())
        edge_group = VGroup(*edges.values())

        # Draw network
        self.play(*[Create(n) for n in nodes.values()], run_time=2)
        self.play(*[GrowArrow(e) for e in edges.values()], run_time=2)

        # Move network
        self.play(node_group.animate.shift(LEFT), edge_group.animate.shift(LEFT), run_time=2)

        # Labels
        labels = {}
        for i, node in nodes.items():
            labels[i] = MathTex(str(i), font_size=48).move_to(node.get_center())
        label_group = VGroup(*labels.values())
        self.play(Write(label_group))
        self.wait(2)