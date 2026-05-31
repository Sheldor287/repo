import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd


def show_layered_graph(G, layers):
    """ Visualize the graph with nodes colored by layer """
    pos = {}
    for i, layer in enumerate(layers):
        for j, node in enumerate(layer):
            pos[node] = (i, -j)  # Position nodes by layer and index

    plt.figure(figsize=(8, 6))
    nx.draw(G, pos, with_labels=True, node_color=[G.nodes[n]['layer'] for n in G.nodes()], cmap=plt.cm.summer, node_size=800)
    plt.title("Layered Graph Visualization")
    plt.show()

def visualize_costflow_graph(H, layers, flow_dict, eps=1e-9):
    """Layered flow visualization with saturation highlighting + edge table"""

    pos = {}

    # Layer layout
    for i, layer in enumerate(layers):
        for j, node in enumerate(layer):
            pos[node] = (i, -j)

    max_layer = len(layers) - 1

    def layer_center(layer_nodes):
        if not layer_nodes:
            return 0
        ys = [-j for j in range(len(layer_nodes))]
        return sum(ys) / len(ys)

    if 'dS' in H.nodes():
        pos['dS'] = (max_layer + 1.5, layer_center(layers[0]))

    if 'dT' in H.nodes():
        pos['dT'] = (-1.5, layer_center(layers[-1]))

    plt.figure(figsize=(10, 7))

    # Node colors by layer (with special colors for artificial nodes)
    node_colors = []
    for n in H.nodes():
        if n == 'dS':
            node_colors.append(-2)
        elif n == 'dT':
            node_colors.append(max_layer + 2)
        else:
            node_colors.append(H.nodes[n].get('layer', 0))

    nx.draw_networkx_nodes(H, pos,node_color=node_colors,node_size=800,cmap=plt.cm.summer)

    # Node labels with demand
    node_labels = {}
    for n in H.nodes():
        if n in ['dS', 'dT']:
            node_labels[n] = n
        else:
            demand = H.nodes[n].get('demand', 0)
            node_labels[n] = f"{n}\n(d:{demand})"

    nx.draw_networkx_labels(H, pos, labels=node_labels, font_size=8)


    # Edge styling 
    edge_colors = []
    edge_widths = []
    edge_label = {}

    for (u, v) in H.edges():
        flow = flow_dict.get((u, v), 0)
        cap = H.edges[u, v].get('capacity', float('inf'))

        if u == 'dS' or v == 'dT':
            edge_colors.append("darkgray")
            edge_widths.append(2.0)
            edge_label[(u, v)] = f"{flow}"
            continue

        if cap != float('inf') and abs(flow - cap) <= eps:
            edge_colors.append("red")      # saturated
            edge_widths.append(3.5)
        elif flow > 0:
            edge_colors.append("blue")     # active
            edge_widths.append(2.5)
        else:
            edge_colors.append("lightgray")  # unused
            edge_widths.append(1.0)


    nx.draw_networkx_edges(H, pos,edge_color=edge_colors,width=edge_widths, arrows=True,node_size=1000)
    nx.draw_networkx_edge_labels(H, pos, edge_labels=edge_label, font_size=8, verticalalignment='center_baseline', rotate=False, connectionstyle='arc3,rad=0.1')

    plt.title("Min-Cost Flow (Node Demand + Edge Saturation)")
    plt.axis('off')
    plt.show()

    # Edge Flow Table
    data_array = []
    print("\nEdge Flow Table:")

    for (u, v) in H.edges():
        flow = flow_dict.get((u, v), 0)
        cap = H.edges[u, v].get('capacity', '∞')
        cost = H.edges[u, v].get('cost', 0)
        if flow > 0 or cap != float('inf'):
            data_array.append([(u, v), (flow, cost, cap)])
    
    df = pd.DataFrame(data_array, columns=['Edge', '(Flow, Cost, Capacity)'])
    return df