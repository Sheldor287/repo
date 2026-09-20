from manim import *
import sys
sys.path.append("C:/Users/Drew/Documents/MyFiles/work/manim_files")
from utils import dag
import networkx as nx
import numpy as np

class FordFulkerson:
    def __init__(self, G:nx.DiGraph, sources:list, sinks:list):
        self.G = G
        self.sources = sources
        self.sinks = sinks
        self._initialize_supersources()

    def _initialize_supersources(self):
        self.source = 's'
        self.sink = 't'
        self.capacity = {(u,v): 1 for (u,v) in self.G.edges()}
        self.flow = {(u,v): 0 for (u,v) in self.G.edges()}
        self.steps = [{"path": None, "flow": self.flow.copy(), "delta": 0}]
        self.H = self.G.copy()
        M = len(self.G.edges())
        for s in self.sources:
            self.H.add_edge(self.source, s)
            self.capacity.update({(self.source, s):M})
            self.flow.update({(self.source, s):0})
        for t in self.sinks:
            self.H.add_edge(t, self.sink)
            self.capacity.update({(t, self.sink):M})
            self.flow.update({(t, self.sink):0})

    def residual_graph(self):
        R = nx.DiGraph()
        R.add_nodes_from(self.H.nodes())
        for u, v in self.H.edges():
            # Forward residual capacity
            forward = self.capacity[(u, v)] - self.flow[(u, v)]
            if forward > 0:
                R.add_edge(u, v, capacity=forward)
            # Reverse residual capacity
            backward = self.flow[(u, v)]
            if backward > 0:
                R.add_edge(v, u, capacity=backward)
        return R

    def find_augmenting_path(self):
        R = self.residual_graph()
        if not nx.has_path(R, self.source, self.sink):
            return None
        return nx.shortest_path(R, self.source, self.sink)

    def augment(self, path):
        R_before = self.residual_graph()
        delta = min(R_before[u][v]["capacity"] for u, v in zip(path[:-1], path[1:]))
        for u, v in zip(path[:-1], path[1:]):
            if (u, v) in self.capacity:
                self.flow[(u, v)] += delta
            else:
                self.flow[(v, u)] -= delta

        R_after = self.residual_graph()
        self.steps.append({"path": path, "flow": self.flow.copy(), "delta": delta, "residual_before": R_before, "residual_after": R_after,})
        return delta

    def run(self):
        while True:
            path = self.find_augmenting_path()
            if path is None:
                break
            self.augment(path)
        return self.steps

    def max_flow_val(self):
        return sum(self.flow[self.source, s] for s in self.sources)


class Graph(Scene):
    def __init__(self):
        super().__init__()
        self.G = dag()
        self.nodes, self.edges = {}, {}
        self.arrow_kwargs = {'tip_length': 0.15, 'max_tip_length_to_length_ratio': 1.0, 'buff': 0.33, 'stroke_width': 4}
        self.edge_list = list(self.G.edges())
        # Graph positioning
        self._scale_graph()
        # Identify source/sink layers
        arr = np.array(list(nx.get_node_attributes(self.G, 'layer').values()))
        sinks = np.where(arr == max(arr))[0].tolist()
        sources = np.where(arr == min(arr))[0].tolist()
        # Run Ford-Fulkerson before animation
        self.ff = FordFulkerson(self.G, sources, sinks)
        self.ff.run()

    def construct(self):
        # GRAPH
        self._create_graph_elements()
        self._create_groups()
        self.play(*[Create(n) for n in self.nodes.values()], run_time=2)
        self.play(*[GrowArrow(e) for e in self.edges.values()], run_time=2)
        self._add_edge_updaters()
        self._get_labels()
        self._get_flow_labels()
        self._get_capacity_labels()
        self.wait(1)

        # ALGORITHM DISPLAY
        self._create_algorithm_labels()
        self.wait(1)
        # FORD-FULKERSON ITERATIONS
        for k, step in enumerate(self.ff.steps[1:], start=1):
            self._animate_step(k, step)

        # FINAL RESULT
        self._show_final_flow()
        self.wait(3)

    # GRAPH CREATION
    def _create_graph_elements(self):
        # Nodes
        for i, val in self.pos.items():
            self.nodes[i] = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
            self.nodes[i].move_to(val)

        # Edges
        for u, v in self.edge_list:
            self.edges[(u, v)] = Arrow(self.nodes[u].get_center(), self.nodes[v].get_center(), **self.arrow_kwargs)

    def _add_edge_updaters(self):
        for (u, v), edge in self.edges.items():
            # Store current color on edge
            edge.color_state = WHITE
            edge.add_updater(lambda e, u=u, v=v: e.become(Arrow(self.nodes[u].get_center(), self.nodes[v].get_center(), color=e.color_state, **self.arrow_kwargs)))

    def _create_groups(self):
        self.node_group = VGroup(*self.nodes.values())
        self.edge_group = VGroup(*self.edges.values())

    # NODE LABELS
    def _get_labels(self):
        self.labels = {}
        for i, node in self.nodes.items():
            label = MathTex(str(i), font_size=48).move_to(node.get_center())
            label.add_updater(lambda l, node=node: l.move_to(node.get_center()))
            self.labels[i] = label
        self.label_group = VGroup(*self.labels.values())
        self.play(*[Write(l) for l in self.labels.values()], run_time=2)

    # FLOW LABELS
    def _get_flow_labels(self):
        self.flow_labels = {}
        for u, v in self.G.edges():
            label = MathTex("0", font_size=32)
            label.add_updater(lambda l, u=u, v=v: self._position_edge_label(l, u, v))
            # Initialize using same position as updater
            self._position_edge_label(label, u, v)
            self.flow_labels[(u, v)] = label
        self.play(*[Write(label) for label in self.flow_labels.values()], run_time=1)

    # EDGE CAPACITY LABELS
    def _get_capacity_labels(self):
        self.capacity_labels = {}
        self.displayed_flow = {(u, v): 0 for u, v in self.G.edges()}
        for u, v in self.G.edges():
            label = MathTex("0/1", font_size=26)
            label.add_updater(lambda l, u=u, v=v: self._position_capacity_label(l, u, v))
            self._position_capacity_label(label, u, v)
            self.capacity_labels[(u, v)] = label
        self.play(*[Write(label) for label in self.capacity_labels.values()], run_time=1)

    def _position_edge_label(self, label, u, v):
        p1 = self.nodes[u].get_center()
        p2 = self.nodes[v].get_center()
        direction = p2 - p1
        direction /= np.linalg.norm(direction[:2])
        normal = np.array([-direction[1], direction[0], 0])
        # 25% of the way from u -> v
        position = (0.75 * p1 + 0.25 * p2)
        label.move_to(position + 0.2 * normal)

    def _position_capacity_label(self, label, u, v):
        p1 = self.nodes[u].get_center()
        p2 = self.nodes[v].get_center()
        direction = p2 - p1
        direction /= np.linalg.norm(direction[:2])
        normal = np.array([-direction[1], direction[0], 0])
        position = 0.4 * p1 + 0.6 * p2
        label.move_to(position + 0.2 * normal)


    # ALGORITHM DISPLAY
    def _create_algorithm_labels(self):
        self.algorithm_title = MathTex(r"\text{Ford--Fulkerson}", font_size=36)
        self.algorithm_title.to_corner(UL, buff=0.4)
        self.iteration_label = MathTex(r"\text{Iteration:}0", font_size=30)
        self.iteration_label.next_to(self.algorithm_title, DOWN, aligned_edge=LEFT, buff=0.15)
        self.delta_label = MathTex(r"\Delta = 0", font_size=30)
        self.delta_label.next_to(self.iteration_label, DOWN, aligned_edge=LEFT, buff=0.15)
        self.flow_value_label = MathTex(r"\text{Flow} = 0", font_size=30)
        self.flow_value_label.to_corner(UR, buff=0.4)
        self.play(
            Write(self.algorithm_title),
            Write(self.iteration_label),
            Write(self.delta_label),
            Write(self.flow_value_label),
            run_time=1
        )

    # ITERATION ANIMATION
    def _animate_step(self, k, step):
        path = step["path"]
        flow = step["flow"]
        delta = step["delta"]
        # Update iteration
        new_iteration = MathTex(rf"\text{{Iteration:}}{k}", font_size=30)
        new_iteration.move_to(self.iteration_label)
        # Update delta
        new_delta = MathTex(rf"\Delta = {delta}", font_size=30)
        new_delta.move_to(self.delta_label)
        # Update flow value
        flow_value = sum(flow[self.ff.source, s] for s in self.ff.sources)
        new_flow = MathTex(rf"\text{{Flow}} = {flow_value}", font_size=30)
        new_flow.move_to(self.flow_value_label)

        self.play(
            FadeTransform(self.iteration_label, new_iteration), 
            FadeTransform(self.delta_label, new_delta), 
            FadeTransform(self.flow_value_label, new_flow), 
            run_time=0.5
            )
        self.iteration_label = new_iteration
        self.delta_label = new_delta
        self.flow_value_label = new_flow
        # Highlight augmenting path
        self._highlight_path(path)
        self.wait(0.5)
        # Update flow labels
        self._update_flow_labels(flow)
        self._update_capacity_labels(flow)
        self.wait(1.25)

    # PATH HIGHLIGHTING
    def _highlight_path(self, path):
        path_edges = []
        for u, v in zip(path[:-1], path[1:]):
            if (u, v) not in self.edges:
                continue
            edge = self.edges[(u, v)]
            path_edges.append(edge)
        def animate_edge_color(edge, alpha):
            edge.color_state = interpolate_color(WHITE, PURE_GREEN, alpha)
        animations = [UpdateFromAlphaFunc(edge, lambda edge, alpha: animate_edge_color(edge, alpha)) for edge in path_edges]
        if animations:
            self.play(*animations, run_time=1, rate_func=smooth)

    # FLOW LABEL UPDATE
    def _update_flow_labels(self, flow):
        animations = []
        replacements = []
        for u, v in self.G.edges():
            old_value = self._flow_value_from_label(self.flow_labels[(u, v)])
            new_value = flow[(u, v)]
            if old_value == new_value:
                continue
            old_label = self.flow_labels[(u, v)]
            # Freeze old label
            old_label.clear_updaters()
            position = old_label.get_center()
            new_label = MathTex(str(new_value), font_size=32)
            new_label.move_to(position)
            replacements.append((u, v, old_label, new_label))
            animations.append(AnimationGroup(FadeOut(old_label), FadeIn(new_label)))
        if animations:
            self.play(*animations, run_time=0.5)
        # Restore label updaters
        for u, v, old_label, new_label in replacements:
            self.flow_labels[(u, v)] = new_label
            new_label.add_updater(lambda l, u=u, v=v: self._position_edge_label(l, u, v))

    # CAPACITY LABEL UPDATE
    def _update_capacity_labels(self, flow):
        animations = []
        for (u, v), label in self.capacity_labels.items():
            new_flow = flow[(u, v)]
            if new_flow != self.displayed_flow[(u, v)]:
                new_label = MathTex(f"{new_flow}/1", font_size=26)
                new_label.move_to(label.get_center())
                animations.append(AnimationGroup(FadeOut(label), FadeIn(new_label)))
                self.capacity_labels[(u, v)] = new_label
                self.displayed_flow[(u, v)] = new_flow
                new_label.add_updater(lambda l, u=u, v=v: self._position_capacity_label(l, u, v))
        if animations:
            self.play(*animations, run_time=0.5)

    def _flow_value_from_label(self, label):
        # Labels are MathTex objects containing a single integer
        try:
            return int(label.tex_string)
        except Exception:
            return 0

    # RESET PATH COLORS
    def _reset_edge_colors(self):
        animations = []
        for edge in self.edges.values():
            if edge.color_state != WHITE:
                animations.append(UpdateFromAlphaFunc(edge, lambda edge, alpha: setattr(edge, "color_state", interpolate_color(PURE_GREEN, WHITE, alpha))))
        if animations:
            self.play(*animations, run_time=0.5, rate_func=smooth)

    # FINAL RESULT
    def _show_final_flow(self):
        max_flow = self.ff.max_flow_val()
        final_label = MathTex(rf"\text{{Maximum Flow}} = {max_flow}", font_size=38)
        final_label.move_to(self.flow_value_label)
        self.play(FadeTransform(self.flow_value_label, final_label), run_time=0.75)
        self.flow_value_label = final_label
        # Emphasize final flow-carrying edges
        flow_edges = []
        for (u, v), edge in self.edges.items():
            if self.ff.flow[(u, v)] > 0:
                flow_edges.append(edge)
        def animate_final_edge(edge, alpha):
            edge.color_state = interpolate_color(WHITE, PURE_GREEN, alpha)
        animations = [UpdateFromAlphaFunc(edge, lambda edge, alpha: animate_final_edge(edge, alpha)) for edge in flow_edges]
        if animations:
            self.play(*animations, run_time=1)

    def _scale_graph(self):
        raw_pos = nx.get_node_attributes(self.G, 'pos')
        nodes = list(raw_pos.keys())
        coords = np.array([raw_pos[n] for n in nodes])
        min_xy = coords.min(axis=0)
        max_xy = coords.max(axis=0)
        center = (min_xy + max_xy) / 2
        centered_coords = (coords - center)
        range_x = (max_xy[0] - min_xy[0])
        range_y = (max_xy[1] - min_xy[1])
        range_x = (range_x if range_x > 0 else 1.0)
        range_y = (range_y if range_y > 0 else 1.0)
        margin_x = 5
        margin_y = 3
        target_width = (config.frame_width - margin_x)
        target_height = (config.frame_height - margin_y)
        scale_x = (target_width / range_x)
        scale_y = (target_height / range_y)
        self.pos = {node: np.array([centered_coords[i][0] * scale_x, centered_coords[i][1] * scale_y, 0]) for i, node in enumerate(nodes)}