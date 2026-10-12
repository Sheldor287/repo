import networkx as nx
import numpy as np

class ToyMultipartite:
    """ Multipartite Graph Constructor"""
    def __init__(self, layer_list=None, is_fully_connected=True, graph_type='DiGraph', seed=123, p=0.75):
        self.G = nx.Graph() if graph_type != 'DiGraph' else nx.DiGraph() 
        self.layer_list = [1,2,2,1] if layer_list is None else layer_list 
        self.is_fully_connected = True if is_fully_connected == True else False  
        self.seed = seed 
        self.generate_p = p 
        self.create_layers()
        self.assign_properties()

    def create_layers(self, node_id=0):
        self.layers_by_idx = []
        for i, size in enumerate(self.layer_list):
            layer = []
            for _ in range(size):
                self.G.add_node(node_id, layer=i)
                layer.append(node_id)
                node_id += 1
            self.layers_by_idx.append(layer)

        for i in range(len(self.layers_by_idx)-1):
            for u in self.layers_by_idx[i]:
                for v in self.layers_by_idx[i+1]:
                    if self.is_fully_connected == True:
                        self.G.add_edge(u,v)
                    else:
                        rng = np.random(seed=self.seed)
                        if rng.random() <= self.generate_p:
                            self.G.add_edge(u,v)

    def assign_properties(self):
        largest_layer = max(self.layer_list)
        layers = self.layers_by_idx
        self.total_demand = np.random.randint(largest_layer, 3 * largest_layer)
        self.layer_0_nodes = [n for n in self.G.nodes() if self.G.nodes[n]['layer'] == 0]
        self.layer_n_nodes = [n for n in self.G.nodes() if self.G.nodes[n]['layer'] == len(layers) - 1]
        self.roles = ['A', 'B', 'C']
        self.power = ['low', 'medium', 'high']
        self._demand_assignment()
        self._node_data_assignment()
        self._edge_data_assignment()

    def _demand_assignment(self):
        for n in self.G.nodes():
            self.G.nodes[n]['demand'] = 0
        while -sum(self.G.nodes[n]['demand'] for n in self.layer_0_nodes) < self.total_demand:
            for n in self.layer_0_nodes:
                if -sum(self.G.nodes[n]['demand'] for n in self.layer_0_nodes) == self.total_demand:
                    break
                if n in self.layers_by_idx[0]:  # Source layer
                    self.G.nodes[n]['demand'] -= np.random.randint(0, 2)
        while sum(self.G.nodes[n]['demand'] for n in self.layer_n_nodes) < self.total_demand:
            for n in self.layer_n_nodes:
                if sum(self.G.nodes[n]['demand'] for n in self.layer_n_nodes) == self.total_demand:
                    break
                if n in self.layers_by_idx[-1]:  # Sink layer
                    self.G.nodes[n]['demand'] += np.random.randint(0, 2)

    def _node_data_assignment(self, layer_role_assign=None, solid_layers=[]):
        for n in self.G.nodes():
            self.G.nodes[n]['probability1'] = np.random.uniform(0.6, 1)
            self.G.nodes[n]['probability2'] = np.random.uniform(0.6, 1)
            self.G.nodes[n]['cost'] = np.random.randint(1, 10)
            self.G.nodes[n]['loc_region'] = (-5,5)
            self.G.nodes[n]['loc'] = (np.random.uniform(-5, 5), np.random.uniform(-5,5))
            if self.G.nodes[n]['layer'] in solid_layers:
                    self.G.nodes[n]['probability1'] = 0.99
                    self.G.nodes[n]['probability2'] = 0.99
                    self.G.nodes[n]['power'] = self.power
                    self.G.nodes[n]['role'] = ['A', 'B', 'C']
            else:
                self.G.nodes[n]['power'] = np.random.choice(self.power, size=np.random.randint(1, len(self.power)+1), replace=False).tolist()
                if not layer_role_assign:
                    self.G.nodes[n]['role'] = np.random.choice(self.roles, size=np.random.randint(2, len(self.power)+1), replace=False).tolist()
                else:
                    self.G.nodes[n]['role'] = layer_role_assign[self.G.nodes[n]['layer']]
                    self.G.nodes[n]['power'] = np.random.choice(self.power, size=2, replace=False).tolist()

    def _edge_data_assignment(self, constant_capacity=False):
            for u, v in self.G.edges():
                self.G.edges[u, v]['performance'] = np.random.rand()*100
                self.G.edges[u, v]['cost'] = np.random.rand()*100
                if constant_capacity == True:
                    self.G.edges[u, v]['capacity'] = 1
                else:
                    self.G.edges[u,v]['capacity'] = np.random.randint(1, 6)

class ToyShell:
    def __init__(self, seed=123):
        self.rng = np.random.default_rng(seed=seed)
        # Wrapper
        self.G = self._random_config()
        self._create_params()
        self._assign_params_to_g()

    def _random_config(self, shell_constructor:list=[(20,60, 0.7), (10, 40, 0.25)], choices:int=10, n:int=6, c_num:int=3):
        self.G = nx.random_shell_graph(shell_constructor, seed=123).to_directed()
        val = self.rng.random()
        self.G.remove_edges_from([(u, v) for u, v in self.G.edges() if u>v and self.rng.random() < val])
        nodes_without_zero = [n for n in self.G.nodes() if n != 0]
        node_subsets = []
        for _ in range(c_num):
            num_dec = 0
            while num_dec < n:
                nodes = np.append(np.array(self.rng.choice(nodes_without_zero, size=choices, replace=False)), 0)
                subgraph = self.G.subgraph(nodes)
                num_dec = len(nx.descendants(subgraph, 0))
            node_subsets.append(nodes)
        self.subgraphs = [self.G.subgraph(nodes) for nodes in node_subsets]
        return self.G

    def _create_params(self):
        self.node_params1 = {n: (self.rng.integers(20, 30), self.rng.integers(1, 10)) for n in self.G.nodes()}
        self.node_params2 = {n: (self.rng.uniform(10, 20), self.rng.uniform(1, 3)) for n in self.G.nodes()}

        self.edge_params1 = {(u, v): (self.rng.integers(20,30), self.rng.integers(1, 10)) for u, v in self.G.edges()}
        self.edge_params2 = {(u, v): (self.rng.uniform(10, 20), self.rng.uniform(0, 2), self.rng.uniform(0.5, 3)) for u, v in self.G.edges()}
        self.edge_params3 = {
            (u, v): (
                (self.rng.integers(1, 10), self.rng.integers(1, 10)), 
                (self.rng.integers(1, 10), self.rng.integers(1, 10))
                ) for u, v in self.G.edges()
                }
        self.edge_params4 = {(u, v): (self.rng.uniform(0, 1), self.rng.uniform(0, 1)) for u, v in self.G.edges()}

    def _assign_params_to_g(self):
        for par, str in zip([self.node_params1, self.node_params2,], ['node_params1', 'node_params2',]):
            nx.set_node_attributes(self.G, par, str)

        for par, str in zip(
            [self.edge_params1, self.edge_params2, self.edge_params3, self.edge_params4],
            ['edge_params1', 'edge_params2', 'edge_params3', 'edge_params4']
        ):
            nx.set_edge_attributes(self.G, par, str)

class ToyBarabasi:
    def __init__(self, seed=123, cutoff: float=0.5):
        self.rng = np.random.default_rng(seed=seed)
        # Wrapper
        self.G = self._random_config(cutoff=cutoff)
        self._create_params()
        self._assign_params_to_g()

    def _random_config(self, constructor:list=[30, 2, 0.6, 0.3], choices:int=10, n:int=6, c_num:int=3, cutoff: float=0.5):
        self.G = nx.extended_barabasi_albert_graph(*constructor, seed=123).to_directed()
        val = self.rng.random()
        self.G.remove_edges_from([(u, v) for u, v in self.G.edges() if self.rng.random() < cutoff])
        nodes_without_zero = [n for n in self.G.nodes() if n != 0]
        node_subsets = []
        for _ in range(c_num):
            num_dec = 0
            while num_dec < n:
                nodes = np.append(np.array(self.rng.choice(nodes_without_zero, size=choices, replace=False)), 0)
                subgraph = self.G.subgraph(nodes)
                num_dec = len(nx.descendants(subgraph, 0))
            node_subsets.append(nodes)
        self.subgraphs = [self.G.subgraph(nodes) for nodes in node_subsets]
        return self.G

    def _create_params(self):
        self.node_params1 = {n: (self.rng.integers(20, 30), self.rng.integers(1, 10)) for n in self.G.nodes()}
        self.node_params2 = {n: (self.rng.uniform(10, 20), self.rng.uniform(1, 3)) for n in self.G.nodes()}

        self.edge_params1 = {(u, v): (self.rng.integers(20,30), self.rng.integers(1, 10)) for u, v in self.G.edges()}
        self.edge_params2 = {(u, v): (self.rng.uniform(10, 20), self.rng.uniform(0, 2), self.rng.uniform(0.5, 3)) for u, v in self.G.edges()}
        self.edge_params3 = {
            (u, v): (
                (self.rng.integers(1, 10), self.rng.integers(1, 10)), 
                (self.rng.integers(1, 10), self.rng.integers(1, 10))
                ) for u, v in self.G.edges()
                }
        self.edge_params4 = {(u, v): (self.rng.uniform(0, 1), self.rng.uniform(0, 1)) for u, v in self.G.edges()}

    def _assign_params_to_g(self):
        for par, str in zip([self.node_params1, self.node_params2,], ['node_params1', 'node_params2',]):
            nx.set_node_attributes(self.G, par, str)

        for par, str in zip(
            [self.edge_params1, self.edge_params2, self.edge_params3, self.edge_params4],
            ['edge_params1', 'edge_params2', 'edge_params3', 'edge_params4']
        ):
            nx.set_edge_attributes(self.G, par, str)

