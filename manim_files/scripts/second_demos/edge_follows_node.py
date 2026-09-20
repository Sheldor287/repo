from manim import *
import sys
sys.path.append("C:/Users/Drew/Documents/MyFiles/work/manim_files")
from utils import dag
import networkx as nx
import numpy as np

class Graph(Scene):
    def __init__(self):
        super().__init__()
        self.G = dag()
        self.nodes, self.edges = {}, {}
        self.arrow_kwargs = {'tip_length': 0.15, 'max_tip_length_to_length_ratio': 1.0, 'buff': 0.33,'stroke_width':4}
        self.edge_list = list(self.G.edges())
        self._scale_graph() # get pos dictionary

    def construct(self):
        self._create_graph_elements()
        self._create_groups()

        self.play(*[Create(n) for n in self.nodes.values()], run_time=2)
        self.play(*[GrowArrow(e) for e in self.edges.values()], run_time=2)
        self._add_edge_updaters()
        self.wait(1)
        self.play(self.node_group.animate.shift(LEFT), self.edge_group.animate.shift(LEFT), run_time=2)
        self.wait(2)
        self._get_labels()
        self.wait(2)
        self.play(self.nodes[0].animate.shift(0.8*UP), run_time=2)
        self.wait(2)
        
    def _create_graph_elements(self):
        # nodes and locations
        for i, val in self.pos.items():
            self.nodes[i] = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
            self.nodes[i].move_to(val)

        """ Updater needs edges and nodes paired together """
        for u, v in self.edge_list:
            self.edges[(u,v)] = Arrow(self.nodes[u].get_center(), self.nodes[v].get_center(), **self.arrow_kwargs)
            
    def _add_edge_updaters(self):
        for (u, v), edge in self.edges.items():
            edge.add_updater(lambda e, u=u, v=v:e.become(Arrow(self.nodes[u].get_center(), self.nodes[v].get_center(), **self.arrow_kwargs)))

    def _create_groups(self):
        self.node_group = VGroup(*self.nodes.values())
        self.edge_group = VGroup(*self.edges.values())

    def _get_labels(self):
        self.labels = {}
        for i, node in self.nodes.items():
            label = MathTex(str(i), font_size=48).move_to(node.get_center())
            label.add_updater(lambda l, node=node: l.move_to(node.get_center()))
            self.labels[i] = label
        self.label_group = VGroup(*self.labels.values())
        self.play(*[Write(l) for l in self.labels.values()], run_time=2)

    def _scale_graph(self):
        raw_pos = nx.get_node_attributes(self.G, 'pos')
        coords = np.array(list(raw_pos.values()))
        # Center the graph
        center = (coords.min(axis=0) + coords.max(axis=0)) / 2
        coords = coords - center
        # Fit to Manim's frame, with a margin
        frame_x = config.frame_width / 1.1
        frame_y = config.frame_height / 2
        margin = 0.9
        scale_x = (frame_x - margin) / np.max(np.abs(coords[:, 0]))
        scale_y = (frame_y - margin) / np.max(np.abs(coords[:, 1]))
        scale = min(scale_x, scale_y)
        self.pos = {node: np.append(coords[i] * scale, 0) for i, node in enumerate(raw_pos)}
