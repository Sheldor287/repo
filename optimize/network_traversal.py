import networkx as nx

class Endpoint_Calculator:
    """ 
    There are functionalities that nx does not have. Customized traversal methods are required for this motivation:

        Suppose there exists a graph G with the following branches: 
            0 --> 1 --> 2 <--> 3
            0 --> 100 --> 2 --> 4 
        Typically, endpoints are calcuated by considering all nodes with out-degree 0 
            OR nodes with the only out degree such that out-nodes are artifical. 
        Finding node 4 in endpoint calcuations is trival by looking at breadth-first-search predecessors.
        Neither out-degree, nor bfs-predecssors can identify 3 as an endpoint. Therefore, this class is a requirement.  
        Finally, if node 2 is part of a larger cycle, it may not be identified as an endpoint by condtion (1) and (3) alone,
        therefore condtion (2) fast-tracks the identification of endpoints for when out-degree = 1. 
    """
    def __init__(self, g: nx.DiGraph):
            self.graph = g
            self.adj = dict(g.adjacency())

    def new_graph(self, g: nx.DiGraph):
        self.graph = g
        self.adj = dict(g.adjacency())

    def find_branch_endpoints(self, start_node):
        # BFS shortest paths and depths
        paths = nx.single_source_shortest_path(self.graph, start_node)
        depth = {node: len(path) - 1 for node, path in paths.items()}
        reachable = set(paths)
        endpoints = set()
        # Restrict the graph to nodes reachable from the start
        graph = self.graph.subgraph(reachable)
        endpoints = set()
        for node in reachable:
            successors = list(graph.successors(node))
            # Condition 1: True sink
            if not successors:
                endpoints.add(node)
                continue
            # Condition 2: Single outgoing edge returning to a shallower BFS layer
            if (len(successors) == 1 and depth[successors[0]] < depth[node]):
                endpoints.add(node)
                continue
            # Condition 3: No distinct reachable node at the same or a deeper layer
            descendants = nx.descendants(graph, node)
            has_forward_continuation = any(depth[other] >= depth[node] for other in descendants if other != node)
            if not has_forward_continuation:
                endpoints.add(node)
        return list(endpoints)
