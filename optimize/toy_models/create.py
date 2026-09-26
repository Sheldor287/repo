import networkx as nx
import numpy as np

class ToyGraph:
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







