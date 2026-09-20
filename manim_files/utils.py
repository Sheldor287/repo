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

