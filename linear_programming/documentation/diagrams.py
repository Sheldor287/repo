import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

class GraphPlots:

    def __init__(self, subsets:iter=None):
        self.G = nx.complete_multipartite_graph(*subsets).to_directed() if subsets is not None else nx.complete_multipartite_graph(1,2,2,1).to_directed()
        self.subset = nx.get_node_attributes(self.G, 'subset')
        self.G.remove_edges_from([(u, v) for u, v in self.G.edges if self.subset[v] - self.subset[u] != 1])

    def plot_xts_graph(self):
        # Construct the graph
        G = self.G.copy()
        max_subset = max(self.subset.values())
        G.add_node('s', subset=-1)
        G.add_node('t', subset=max_subset+1)
        artificial_edges = [('s', i) for i,d in G.nodes(data=True) if d['subset']==0]
        artificial_edges.extend([(i, 't') for i,d in G.nodes(data=True) if d['subset']==max_subset])
        artificial_edges.extend([('t', 's')])
        G.add_edges_from(artificial_edges)

        # Layout position
        pos = nx.multipartite_layout(G)
        plt.figure(figsize=(10, 4))
        # Draw nodes & labels
        nx.draw_networkx_nodes(G, pos, node_color=['skyblue' if type(n) is int else 'lightgrey' for n in G.nodes], node_size=400)
        nx.draw_networkx_labels(G, pos, font_weight='bold')
        normal_edges = [e for e in G.edges if e != ('t', 's')]
        loop_edge = [('t', 's')]
        nx.draw_networkx_edges(
            G, pos, edgelist=normal_edges, arrows=True, 
            edge_color=['black' if (u,v) not in artificial_edges else 'lightgrey' for (u,v) in normal_edges]
            )
        nx.draw_networkx_edges(G, pos, edgelist=loop_edge, connectionstyle="arc3,rad=-0.5", arrows=True, edge_color='lightgrey')
        plt.axis('off')
        plt.show()


    def return_example_graph(self, plot=True, seed=123):
        if plot:
            pos = nx.multipartite_layout(self.G)
            plt.figure(figsize=(7,4))
            nx.draw(self.G, pos, node_color='skyblue', font_weight='bold', with_labels=True, node_size=400)

        np.random.seed(seed)
        for _,_,d in self.G.edges(data=True):
            d['leader_cost'] = np.random.uniform(2, 5)
            d['capacity'] = np.random.randint(1, 5)
        for _,d in self.G.nodes(data=True):
            d['follower_cost'] = np.random.uniform(5, 10)
        return self.G

