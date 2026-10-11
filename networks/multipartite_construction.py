import matplotlib.pyplot as plt
import networkx as nx 

G = nx.complete_multipartite_graph(1, 3, 10, 10, 4, 3, 2, 1).to_directed()
subset = nx.get_node_attributes(G, 'subset')
edges = [(u,v) for u, v in G.edges() if subset[v] - subset[u] != 1]
G.remove_edges_from(edges)
plt.figure(figsize=(16, 7))
nx.draw(G, pos=nx.multipartite_layout(G), arrowsize=4, node_color='skyblue', with_labels=True, font_weight='bold', node_size=500)
plt.show()