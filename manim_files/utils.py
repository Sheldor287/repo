import sys
import random
import numpy as np
import networkx as nx
sys.path.append("C:/Users/Drew/Documents/MyFiles/work")
from networks.dep_src.graph_utils import create_layered_graph, assign_properties

def dag(layer_sizes=[2, 4, 5, 3], remove_fraction=0.8, seed=123):
    random.seed(seed)
    np.random.seed(seed)
    G, _ = create_layered_graph(layer_sizes)
    G = assign_properties(G, layer_sizes)
    pos = nx.multipartite_layout(G, subset_key='layer')
    for n, d in G.nodes(data=True):
        d['pos'] = pos[n]
    return remove_edges_balanced(G, remove_fraction=remove_fraction)

def remove_edges_balanced(G, remove_fraction=0.6):
    H = G.copy()
    candidate_edges = list(H.edges())
    target_removals = int(len(candidate_edges) * remove_fraction)
    removed_count = 0
    layers = [data['layer'] for _, data in G.nodes(data=True) if 'layer' in data]
    min_layer, max_layer = min(layers), max(layers)
    sources = {node for node, data in G.nodes(data=True) if data.get('layer') == min_layer}
    sinks = {node for node, data in G.nodes(data=True) if data.get('layer') == max_layer}
    intermediate_nodes = {node for node, data in G.nodes(data=True) if data.get('layer') not in (min_layer, max_layer)}
    def _is_valid(g):
        for s in sources:
            if not any(nx.has_path(g, s, t) for t in sinks):
                return False
        for t in sinks:
            if not any(nx.has_path(g, s, t) for s in sources):
                return False
        for node in intermediate_nodes:
            if g.in_degree(node) == 0 or g.out_degree(node) == 0:
                return False
        return True
    while candidate_edges and removed_count < target_removals:
        edge = random.choice(candidate_edges)
        candidate_edges.remove(edge)
        u, v = edge
        H.remove_edge(u, v)
        if not _is_valid(H):
            H.add_edge(u, v)
        else:
            removed_count += 1
    return H

class FordFulkerson:
    def __init__(self, G: nx.DiGraph, sources: list, sinks: list):
        self.G = G.copy()
        self.sources = sources
        self.sinks = sinks
        
        for _, _, d in self.G.edges(data=True):
            if "capacity" not in d:
                d["capacity"] = 1
                
        self._initialize_supersources()

    def _initialize_supersources(self):
        self.source = 's'
        self.sink = 't'
        
        self.H = self.G.copy()
        self.capacity = {(u, v): d.get('capacity', 1) for u, v, d in self.G.edges(data=True)}
        self.flow = {(u, v): 0 for (u, v) in self.G.edges()}
        
        M = sum(self.capacity.values()) if self.capacity else 1
        
        for s in self.sources:
            self.H.add_edge(self.source, s)
            self.capacity[(self.source, s)] = M
            self.flow[(self.source, s)] = 0
            
        for t in self.sinks:
            self.H.add_edge(t, self.sink)
            self.capacity[(t, self.sink)] = M
            self.flow[(t, self.sink)] = 0
            
        self.steps = []

    def residual_graph(self):
        R = nx.DiGraph()
        R.add_nodes_from(self.H.nodes())
        for u, v in self.H.edges():
            forward = self.capacity[(u, v)] - self.flow[(u, v)]
            if forward > 0:
                R.add_edge(u, v, capacity=forward)
            backward = self.flow[(u, v)]
            if backward > 0:
                R.add_edge(v, u, capacity=backward)
        return R

    def find_augmenting_path(self, strategy="dfs"):
        R = self.residual_graph()
        if not nx.has_path(R, self.source, self.sink):
            return None
            
        if strategy == "bfs":
            return nx.shortest_path(R, self.source, self.sink)
        else:
            # DFS search on active residual graph R (supports backward edges)
            try:
                return next(nx.all_simple_paths(R, self.source, self.sink))
            except StopIteration:
                return None

    def augment(self, path):
        R_before = self.residual_graph()
        delta = min(R_before[u][v]["capacity"] for u, v in zip(path[:-1], path[1:]))
        
        for u, v in zip(path[:-1], path[1:]):
            if (u, v) in self.capacity:
                self.flow[(u, v)] += delta
            else:
                self.flow[(v, u)] -= delta

        R_after = self.residual_graph()
        self.steps.append({
            "path": path,
            "flow": self.flow.copy(),
            "delta": delta,
            "residual_before": R_before,
            "residual_after": R_after
        })
        return delta

    def run(self, strategy="dfs"):
        while True:
            path = self.find_augmenting_path(strategy=strategy)
            if path is None:
                break
            self.augment(path)
        return self.steps

    def max_flow_val(self):
        return sum(self.flow[self.source, s] for s in self.sources)