from manim import *
import sys
sys.path.append("C:/Users/Drew/Documents/MyFiles/work/manim_files")
from utils import FordFulkerson, dag
import networkx as nx
import numpy as np

class Graph(Scene):
    def __init__(self):
        # get manim methods
        super().__init__()
        # designed example
        self.G = dag([2,3,3,1], remove_fraction=0.1)
        arr = np.array(list(nx.get_node_attributes(self.G, 'layer').values()))
        sinks = np.where(arr == max(arr))[0].tolist()
        sources = np.where(arr == min(arr))[0].tolist()
        self.G.add_edges_from([(7,6), (6,5)])
        np.random.seed(123)
        for u,v,d in self.G.edges(data=True):
            #if u in [0,1] or v in [8,9]:
            d['capacity'] = np.random.randint(5,15)
            #else:
            #    d['capacity'] = np.random.randint(1,3)

        self.nodes, self.edges = {}, {}
        self.arrow_kwargs = {'tip_length': 0.15, 'max_tip_length_to_length_ratio': 1.0, 'buff': 0.33, 'stroke_width': 4}
        self.edge_list = list(self.G.edges())
        self.CAP_LABEL_SIZE=18
        self.FLOW_LABEL_SIZE=20
        # Graph positioning
        self._scale_graph()
        # Run Ford-Fulkerson before animation
        self.ff = FordFulkerson(self.G, sources, sinks)
        self.ff.run()

    def construct(self):
        # MAKE GRAPH AND LABELS
        self._create_graph_elements()
        self.node_group = VGroup(*self.nodes.values())
        self.edge_group = VGroup(*self.edges.values())
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

    # LABELS
    def _get_labels(self):
        self.labels = {}
        for i, node in self.nodes.items():
            label = MathTex(str(i), font_size=48).move_to(node.get_center())
            label.add_updater(lambda l, node=node: l.move_to(node.get_center()))
            self.labels[i] = label
        self.label_group = VGroup(*self.labels.values())
        self.play(*[Write(l) for l in self.labels.values()], run_time=2)

    def _get_flow_labels(self):
        self.flow_labels = {}
        for u, v in self.G.edges():
            label = MathTex("0", font_size=self.FLOW_LABEL_SIZE)
            label.add_updater(lambda l, u=u, v=v: self._position_edge_label(l, u, v))
            # Initialize using same position as updater
            self._position_edge_label(label, u, v)
            self.flow_labels[(u, v)] = label
        self.play(*[Write(label) for label in self.flow_labels.values()], run_time=1)

    def _get_capacity_labels(self):
        self.capacity_labels = {}
        self.displayed_flow = {(u, v): 0 for u, v in self.G.edges()}
        for u, v, d in self.G.edges(data=True):
            label = MathTex(f"0/{d.get('capacity', 1)}", font_size=self.CAP_LABEL_SIZE)
            label.add_updater(lambda l, u=u, v=v: self._position_capacity_label(l, u, v))
            self._position_capacity_label(label, u, v)
            self.capacity_labels[(u, v)] = label
        self.play(*[Write(label) for label in self.capacity_labels.values()], run_time=1)

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
        self.path_label = MathTex(r"\text{Augmenting Path:}-", font_size=28)
        self.path_label.next_to(self.delta_label, DOWN, aligned_edge=LEFT, buff=0.15)
        self.play(
            Write(self.algorithm_title),
            Write(self.iteration_label),
            Write(self.delta_label),
            Write(self.flow_value_label),
            Write(self.path_label),
            run_time=2
        )

    def _create_path_band(self, path, color):
        band = VGroup()
        if path is None or len(path) < 2:
            return band
        # Keep only nodes that actually exist in the displayed graph.
        display_path = [node for node in path if node in self.nodes]
        if len(display_path) < 2:
            return band
        for u, v in zip(display_path[:-1], display_path[1:]):
            segment = Line(self.nodes[u].get_center(), self.nodes[v].get_center(), stroke_width=16, stroke_opacity=0.30, color=color,)
            band.add(segment)
        return band

    def _find_flow_path(self, flow, required_edge=None):
        sources = self.ff.sources
        sinks = self.ff.sinks
        flow_graph = nx.DiGraph()
        for (u,v), val in flow.items():
            if val > 0:
                flow_graph.add_edge(u,v)
        for source in sources:
            for sink in sinks:
                if source not in flow_graph or sink not in flow_graph:
                    continue
                try:
                    paths = nx.all_simple_paths(flow_graph, source, sink)
                    for path in paths:
                        if required_edge is None:
                            return path
                        # if a specific edge is in the set of reverse edges
                        if required_edge in set(zip(path[:-1], path[1:])):
                            return path
                except:
                    continue # reverse edge leads to a dead-end
        return None

    def _get_reverse_edges(self, path, flow):
        reverse_edges = []
        if path is None:
            return reverse_edges
        for u, v in zip(path[:-1], path[1:]):
            # Residual traversal u -> v is reverse of an original edge v -> u carrying flow.
            if ((v, u) in self.edges and flow.get((v, u), 0) > 0):
                reverse_edges.append((v, u))
        return reverse_edges

    def _find_new_flow_path(self, old_flow, new_flow):
        added_edges = set()
        for edge in new_flow:
            if new_flow[edge] > old_flow.get(edge, 0):
                added_edges.add(edge)
        if not added_edges:
            return None
        sources = self.ff.sources
        sinks = self.ff.sinks
        flow_graph = nx.DiGraph()
        for (u, v), value in new_flow.items():
            if value > 0:
                flow_graph.add_edge(u, v)
        for source in sources:
            for sink in sinks:
                if source not in flow_graph or sink not in flow_graph:
                    continue
                try:
                    paths = nx.all_simple_paths(flow_graph, source, sink)
                    for path in paths:
                        path_edges = set(zip(path[:-1], path[1:]))
                        if path_edges & added_edges:
                            return path
                except nx.NetworkXNoPath:
                    continue
        return None
    
    # ITERATION ANIMATION
    def _animate_step(self, k, step):
        path = step["path"]
        flow = step["flow"]
        delta = step["delta"]
        old_flow = self.ff.steps[k - 1]["flow"]

        # interation data
        new_iteration = MathTex(rf"\text{{Iteration:}}{k}", font_size=30)
        new_iteration.move_to(self.iteration_label)
        # delta update
        new_delta = MathTex(rf"\Delta = {delta}", font_size=30)
        new_delta.move_to(self.delta_label)
        # text update
        path_text = self._format_path(path)
        new_path = MathTex(rf"\text{{Augmenting Path:}}{path_text}", font_size=22)
        new_path.to_corner(DL, buff=0.4)
        # flow values
        flow_value = sum(flow[self.ff.source, s] for s in self.ff.sources)
        new_flow = MathTex(rf"\text{{Flow}} = {flow_value}", font_size=30)
        new_flow.move_to(self.flow_value_label)

        self.play(
            FadeTransform(self.iteration_label, new_iteration),
            FadeTransform(self.delta_label, new_delta),
            FadeTransform(self.path_label, new_path),
            FadeTransform(self.flow_value_label, new_flow),
            run_time=0.5
        )

        self.iteration_label = new_iteration
        self.delta_label = new_delta
        self.path_label = new_path
        self.flow_value_label = new_flow

        # state transition
        animations = []
        animations.extend(self._get_edge_color_animations(path, flow))
        flow_anims, flow_replacements = (self._get_flow_label_animations(flow))
        capacity_anims, capacity_replacements = (self._get_capacity_label_animations(flow))
        animations.extend(flow_anims)
        animations.extend(capacity_anims)
        if animations:
            self.play(*animations, run_time=1.5, rate_func=smooth)

        # CHECK IF RESIDUAL EDGE EXISTS
        reverse_edges = self._get_reverse_edges(path, old_flow)
        if reverse_edges:
            self._animate_flow_reallocation(old_flow, flow, path)


        # Commit new flow labels
        for u, v, new_label in flow_replacements:
            self.flow_labels[(u, v)] = new_label

        # Commit new capacity labels
        for u, v, new_label in capacity_replacements:
            self.capacity_labels[(u, v)] = new_label
            self.displayed_flow[(u, v)] = flow[(u, v)]

        # Hold the complete iteration state
        self.wait(4)

    def _animate_flow_reallocation(self, old_flow, new_flow, residual_path):
        reverse_edges = self._get_reverse_edges(residual_path, old_flow)
        if not reverse_edges:
            return
        # Existing flow route being reallocated
        old_path = None
        for edge in reverse_edges:
            old_path = self._find_flow_path(old_flow, required_edge=edge)
            if old_path is not None:
                break
        if old_path is None:
            return
        red_band = self._create_path_band(old_path, PURE_RED)
        self.play(FadeIn(red_band), run_time=0.6)
        self.wait(2)
        # New source-sink route
        new_path = self._find_new_flow_path(old_flow, new_flow)
        if new_path is None:
            self.play(FadeOut(red_band), run_time=0.5)
            return
        green_band = self._create_path_band(new_path, PURE_GREEN)
        self.play(FadeIn(green_band), run_time=0.6)
        self.wait(2)
        # Remove explanatory bands
        self.play(FadeOut(red_band), FadeOut(green_band), run_time=0.5)

    def _get_edge_color_animations(self, path, flow):
        path_edges = set()
        reverse_edges = set()
        # Identify augmenting-path edges
        if path is not None:
            for u, v in zip(path[:-1], path[1:]):
                if (u, v) in self.edges:
                    path_edges.add((u, v))
                elif (v, u) in self.edges:
                    reverse_edges.add((v, u))
        animations = []
        for (u, v), edge in self.edges.items():
            # Current augmenting path
            if (u, v) in path_edges:
                target_color = PURE_GREEN
            # Reverse traversal through residual graph
            elif (u, v) in reverse_edges:
                target_color = PURE_RED
            # Existing positive flow
            elif flow[(u, v)] > 0:
                target_color = PURE_GREEN
            # No flow
            else:
                target_color = WHITE
            start_color = edge.color_state
            if start_color != target_color:
                animations.append(UpdateFromAlphaFunc(
                        edge,
                        lambda e, alpha,
                            start_color=start_color,
                            target_color=target_color:
                            setattr(e, "color_state", interpolate_color(start_color, target_color, alpha))
                    ))
        return animations

    def _get_flow_label_animations(self, flow):
        animations = []
        replacements = []
        for u, v in self.G.edges():
            old_value = self._flow_value_from_label(self.flow_labels[(u, v)])
            new_value = flow[(u, v)]
            if old_value == new_value:
                continue
            old_label = self.flow_labels[(u, v)]
            old_label.clear_updaters()
            new_label = MathTex(str(new_value), font_size=self.FLOW_LABEL_SIZE)
            new_label.move_to(old_label.get_center())
            new_label.add_updater(lambda l, u=u, v=v: self._position_edge_label(l, u, v))
            replacements.append((u, v, new_label))
            animations.append(ReplacementTransform(old_label, new_label))
        return animations, replacements

    def _get_capacity_label_animations(self, flow):
        animations = []
        replacements = []
        for (u, v), label in self.capacity_labels.items():
            new_flow = flow[(u, v)]
            if new_flow == self.displayed_flow[(u, v)]:
                continue
            capacity = self.G[u][v].get("capacity", 1)
            new_label = MathTex(f"{new_flow}/{capacity}", font_size=self.CAP_LABEL_SIZE)
            new_label.move_to(label.get_center())
            new_label.add_updater(lambda l, u=u, v=v: self._position_capacity_label(l, u, v))
            replacements.append((u, v, new_label))
            animations.append(ReplacementTransform(label, new_label))
        return animations, replacements

    # HELPERS
    def _flow_value_from_label(self, label):
        # Labels are MathTex objects containing a single integer
        try:
            return int(label.tex_string)
        except Exception:
            return 0

    def _format_path(self, path):
        if path is None:
            return ""
        return r" \rightarrow ".join(str(node) for node in path if node not in ['s', 't']) 

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

    # FORMATTING
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

    def _position_edge_label(self, label, u, v):
        p1 = self.nodes[u].get_center()
        p2 = self.nodes[v].get_center()
        direction = p2 - p1
        direction /= np.linalg.norm(direction[:2])
        normal = np.array([-direction[1], direction[0], 0])
        # 25% of the way from u -> v
        position = (0.75 * p1 + 0.25 * p2)
        label.move_to(position + 0.15 * normal)

    def _position_capacity_label(self, label, u, v):
        p1 = self.nodes[u].get_center()
        p2 = self.nodes[v].get_center()
        direction = p2 - p1
        direction /= np.linalg.norm(direction[:2])
        normal = np.array([-direction[1], direction[0], 0])
        position = 0.4 * p1 + 0.6 * p2
        label.move_to(position + 0.15 * normal)


