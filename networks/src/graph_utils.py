import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def create_layered_graph(layer_sizes, fully_connect=True):
    """ Generate a graph from a list of layer sizes """
    G = nx.DiGraph()
    layers = []

    node_id = 0

    # Create nodes layer by layer
    for i, size in enumerate(layer_sizes):
        layer = []
        for j in range(size):
            G.add_node(node_id, layer=i)
            layer.append(node_id)
            node_id += 1
        layers.append(layer)

    # Add edges between layers
    for i in range(len(layers) - 1):
        for u in layers[i]:
            for v in layers[i + 1]:
                if fully_connect:
                    G.add_edge(u, v)

    return G, layers

def build_min_cost_flow_dict(G, layers,cost_dict=None,capacity_dict=None, supply_dict=None, demand_dict=None):

    H = nx.DiGraph()

    # Add demand attribute
    for node in G.nodes():
        H.add_node(node, demand=0, layer=G.nodes[node]['layer'])

    # Supply
    if supply_dict:
        for node in layers[0]:
            val = supply_dict.get(node, np.random.randint(1, 10))
            H.nodes[node]['demand'] -= val
    else: 
        for node in layers[0]:
            val = np.random.randint(1, 10)
            H.nodes[node]['demand'] -= val

    # Demand 
    if demand_dict:
        for node in layers[-1]:
            val = demand_dict.get(node, np.random.randint(1, 10))
            H.nodes[node]['demand'] += val
    else:
        for node in layers[-1]:
            val = np.random.randint(1, 10)
            H.nodes[node]['demand'] += val


    # Add edges with cost + capacity
    for (u, v) in G.edges():
        cost = cost_dict.get((u, v), np.random.randint(1, 10)) if cost_dict else np.random.randint(1, 10)
        cap = capacity_dict.get((u, v), float('inf')) if capacity_dict else float('inf')

        H.add_edge(u, v, cost=cost, capacity=cap)

    return H

def layered_layout(G, s, t):
    levels = {}
    visited = {s}
    queue = [(s, 0)]

    while queue:
        node, level = queue.pop(0)
        levels[node] = level
        for neighbor in G.successors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, level + 1))

    pos = {}
    layer_counts = {}
    for node, level in levels.items():
        layer_counts[level] = layer_counts.get(level, 0) + 1

    layer_positions = {}
    for level, count in layer_counts.items():
        xs = list(range(count))
        layer_positions[level] = xs

    for node, level in levels.items():
        idx = layer_positions[level].pop(0)
        pos[node] = (level, idx)

    return pos

def assign_properties(G, layer_sizes, constant_capacity=False, layer_role_assign=None):
    # Metaparameters
    largest_layer = max(layer_sizes)
    layers = [list(range(sum(layer_sizes[:i]), sum(layer_sizes[:i+1]))) for i in range(len(layer_sizes))]
    total_demand = np.random.randint(largest_layer, 3 * largest_layer)
    layer_0_nodes = [n for n in G.nodes() if G.nodes[n]['layer'] == 0]
    layer_n_nodes = [n for n in G.nodes() if G.nodes[n]['layer'] == len(layers) - 1]
    roles = ['A', 'B', 'C']
    power = ['low', 'medium', 'high']

    # Demand assignment
    for n in G.nodes():
        G.nodes[n]['demand'] = 0
    while -sum(G.nodes[n]['demand'] for n in layer_0_nodes) < total_demand:
        for n in layer_0_nodes:
            if -sum(G.nodes[n]['demand'] for n in layer_0_nodes) == total_demand:
                break
            if n in layers[0]:  # Source layer
                G.nodes[n]['demand'] -= np.random.randint(0, 2)
    while sum(G.nodes[n]['demand'] for n in layer_n_nodes) < total_demand:
        for n in layer_n_nodes:
            if sum(G.nodes[n]['demand'] for n in layer_n_nodes) == total_demand:
                break
            if n in layers[-1]:  # Sink layer
                G.nodes[n]['demand'] += np.random.randint(0, 2)

    # Node data
    for n in G.nodes():
        G.nodes[n]['probability1'] = np.random.uniform(0.6, 1)
        G.nodes[n]['probability2'] = np.random.uniform(0.6, 1)
        G.nodes[n]['cost'] = np.random.randint(1, 10)
        if G.nodes[n]['layer'] in [3, 4]:
                G.nodes[n]['probability1'] = 0.99
                G.nodes[n]['probability2'] = 0.99
                G.nodes[n]['power'] = power
                G.nodes[n]['role'] = ['A', 'B', 'C']
        else:
            G.nodes[n]['power'] = np.random.choice(power, size=np.random.randint(1, len(power)+1), replace=False).tolist()
            if not layer_role_assign:
                G.nodes[n]['role'] = np.random.choice(roles, size=np.random.randint(2, len(roles)+1), replace=False).tolist()
            else:
                G.nodes[n]['role'] = layer_role_assign[G.nodes[n]['layer']]
                G.nodes[n]['power'] = np.random.choice(power, size=2, replace=False).tolist()
            print(f"node: {n}, power: {G.nodes[n]['power']}, roles: {G.nodes[n]['role']}")
    

    # Rewrite graph edges based on power and role attributes 
    G.clear_edges()
    for i in range(len(layers) - 1):
        for u in layers[i]:
            for v in layers[i + 1]:
                for role in roles:
                    for p in power:
                        if G.nodes[u]['layer'] in [2,3,4]:
                            G.add_edge(u, v, role=role, power=p, capacity=10, probability=0.99)
                            continue
                        if (role in G.nodes[u]['role']) and (role in G.nodes[v]['role']) and (p in G.nodes[u]['power']) and (p in G.nodes[v]['power']):
                            if constant_capacity:
                                G.add_edge(u, v, role=role, power=p, capacity=1, probability=np.random.uniform(0.6, 0.99))
                            else:
                                G.add_edge(u, v, role=role, power=p, capacity=np.random.randint(1, 10), probability=np.random.uniform(0.6, 0.99))
                        


    # Edge data
    for u, v in G.edges():
        G.edges[u, v]['performance'] = np.random.rand()*100
        G.edges[u, v]['cost'] = np.random.rand()*100
        if constant_capacity == True:
            G.edges[u, v]['capacity'] = 1
        else:
            G.edges[u,v]['capacity'] = np.random.randint(1, 6)

    return G
