import networkx as nx
def condense_graph(G: nx.DiGraph) -> nx.DiGraph:
    """
    Given a specified dictionary of nodes, condense the graph by removing nonnumeric nodes and connecting numeric nodes directly.
    Each resulting edge stores the intermediate nonnumeric nodes in the 'intermediate_nodes' attribute.
    """
    H = nx.DiGraph()
    # Identify the condition to keep nodes:
    numeric_nodes = {n for n in G.nodes if isinstance(n, (int, float)) and not isinstance(n, bool)}
    # Preserve attributes on retained nodes.
    H.add_nodes_from((n, G.nodes[n].copy()) for n in numeric_nodes)
    for source in numeric_nodes:
        # Explore paths beginning at each numeric node.
        stack = [(neighbor, [neighbor], {source, neighbor}) for neighbor in G.successors(source)]
        while stack:
            node, path, visited = stack.pop()
            if node in numeric_nodes:
                # Reached the next numeric node.
                H.add_edge(source, node, intermediate_nodes=path[:-1], path=[source] + path,)
                continue
            # Continue through nonnumeric nodes.
            for neighbor in G.successors(node):
                if neighbor not in visited:
                    stack.append((neighbor, path + [neighbor], visited | {neighbor},))
    return H

if __name__ == "__main__":
    G = nx.DiGraph([(1, "a"), ("a", "b"), ("b", 2), (1, "c"), ("c", 2), (2, 3),])
    H = condense_graph(G)
    print(f"Original Graph Nodes: {G.nodes()}")
    print(f'Condensed Graph Nodes: {H.nodes()}')
    print(f'Condensed Graph Edges: {H.edges(data=True)}')