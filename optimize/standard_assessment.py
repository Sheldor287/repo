from __future__ import annotations  
from const import PARAMETER_ATTRIBUTES, THRESHOLD_STATES, FEATURE_DISTRIBUTIONS
from scipy.sparse.csgraph import dijkstra
from matplotlib import pyplot as plt
from scipy.sparse import csr_matrix
from scipy.stats import weibull_min
from typing import List, Dict
from tqdm.auto import tqdm
import networkx as nx
import numpy as np

class Sim:
    def __init__(self, G:nx.DiGraph, subgraphs: List[nx.DiGraph], **sim_kwargs):
        # Simulation settings
        self.n_sim = sim_kwargs.get("n_sim", 1000)
        self.seed = sim_kwargs.get("seed", 123)
        # Kwarg parsing
        self.parameter_attributes = sim_kwargs.get("param_names", PARAMETER_ATTRIBUTES)
        self.threshold_states = sim_kwargs.get("state_params", THRESHOLD_STATES)
        self.feature_distributions = sim_kwargs.get("sim_config", FEATURE_DISTRIBUTIONS)
        self.combinations = sim_kwargs.get("combinations", [])
        # Independent, reproducible random streams
        seed_sequence = np.random.SeedSequence(self.seed)
        rngs = seed_sequence.spawn(4)
        # Streams for each distribution type 
        self.rng_node = np.random.default_rng(rngs[0])
        self.rng_edge_score = np.random.default_rng(rngs[1])
        self.rng_edge_cost = np.random.default_rng(rngs[2])
        self.rng_endpoint_score = np.random.default_rng(rngs[3])
        # Graph parameters, indexed by semantic names
        self.G = G
        self.subgraphs = subgraphs
        self.node_params = {"node_score": nx.get_node_attributes(self.G, self.parameter_attributes["node_score"])}
        self.edge_params = {
            name: nx.get_edge_attributes(self.G, attribute) 
            for name, attribute in self.parameter_attributes.items() if name != "node_score"
            }
        # Node/edge constants
        self.nodes = list(self.G.nodes())
        self.edges = list(self.G.edges())
        self.n_nodes = len(self.nodes)
        self.n_edges = len(self.edges)
        self.node_index = {node: i for i, node in enumerate(self.nodes)}
        self.edge_index = {edge: i for i, edge in enumerate(self.edges)}
        self.n_combinations = len(self.combinations)
        self.n_subgraphs = len(self.subgraphs)
        self.feature_space = self.n_nodes + 3 * self.n_edges
        # Pre-construct simulation matrix
        self._configure_simulation_matrix()

    def run_threshold_simulation(self, source_sink_pairs:Dict[int, List[tuple]]):
        """Evaluate reachability and shortest paths into dense result arrays."""
        # Pre-processing steps
        self._configure_graph_matrix()
        self._initialize_path_results(source_sink_pairs)
        N, E = self.n_nodes, self.n_edges
        C, S, M = (self.n_combinations, self.n_subgraphs, self.n_sim,)
        total = C*S*M
        # Ensure subgraphs and cases are processed correctly
        sinks_by_source = {}
        for case, pairs in source_sink_pairs.items():
            subgraph_idx = (int(case.rsplit("_", 1)[1]) if isinstance(case, str) else int(case)) # Standardized indexing
            if not 0 <= subgraph_idx < S:
                raise ValueError(f"Invalid subgraph index: {subgraph_idx}")
            sources = sinks_by_source.setdefault(subgraph_idx, {}) # Standardized indexing
            for source, sink in pairs:
                sources.setdefault(source, set()).add(sink) # Register of source-sink pairs
        # Record (u,v) components of edge-pairs for edge-endpoint tracking
        edge_u = np.fromiter((self.node_index[u] for u, v in self.edges), dtype=int, count=E,)
        edge_v = np.fromiter((self.node_index[v] for u, v in self.edges), dtype=int, count=E,)
        # Main loop
        with tqdm(total=total, desc='Dijkstra Simulation', unit='run') as pbar:
            for subgraph_idx, sources in sinks_by_source.items():
                for combination_idx in range(C):
                    for replication_idx in range(M):
                        # Read the simulated configuration matrices
                        node_available = self.configuration_matrix[:N, combination_idx, subgraph_idx, replication_idx].astype(bool)
                        edge_available = self.configuration_matrix[N:, combination_idx, subgraph_idx, replication_idx].astype(bool)
                        active_edges = (edge_available & node_available[edge_u] & node_available[edge_v])
                        # Reuse the sampled edge costs for this subgraph and replication rather than drawing a second set.
                        edge_costs = self.feature_matrix[N + E:N + 2 * E, subgraph_idx, replication_idx,]
                        graph = csr_matrix((edge_costs[active_edges], (edge_u[active_edges], edge_v[active_edges],),), shape=(N, N),)
                        # Check of sources are active
                        active_sources = [
                            source for source in sources 
                            if source in self.node_index and node_available[self.node_index[source]]
                            ]
                        pbar.update(1)
                        """ Metric Calcuation: """
                        if not active_sources:
                            continue
                        source_indices = [self.node_index[source] for source in active_sources]
                        # Check shortest paths
                        distances = dijkstra(graph, directed=True, indices=source_indices,)
                        distances = np.atleast_2d(distances)
                        # Determine if results can be recorded as successful 
                        for row, source in enumerate(active_sources):
                            source_distances = distances[row]
                            for sink in sources[source]:
                                if sink not in self.node_index:
                                    continue
                                sink_idx = self.node_index[sink]
                                if not node_available[sink_idx]:
                                    continue
                                distance = source_distances[sink_idx]
                                if not np.isfinite(distance):
                                    continue
                                # Record the result
                                result_idx = self.path_pair_index[(subgraph_idx, source, sink)]
                                self.reachability[result_idx, combination_idx, replication_idx] = 1
                                self.shortest_distance[result_idx, combination_idx, replication_idx] = distance
        return self.reachability, self.shortest_distance         

    def plot_threshold_draws(self, config_indices=(1, 14), max_points=5000):
        # Pre-processing
        N, E = self.n_nodes, self.n_edges
        edge_scores = self.feature_matrix[N:N + E].ravel()
        endpoint_scores = self.feature_matrix[N + 2*E:N + 3*E].ravel()
        valid = np.isfinite(edge_scores) & np.isfinite(endpoint_scores)
        x = edge_scores[valid]
        y = endpoint_scores[valid]
        # Subsample for readability without changing the stored data.
        rng = np.random.default_rng(123)
        if len(x) > max_points:
            idx = rng.choice(len(x), max_points, replace=False)
            x, y = x[idx], y[idx]
        fig, axes = plt.subplots(
            1, len(config_indices), figsize=(7 * len(config_indices), 5), 
            sharex=True, sharey=True, squeeze=False,
            )
        axes = axes.ravel()
        # Plot figures
        for ax, c in zip(axes, config_indices):
            thresholds = self.combinations[c]
            edge_t = thresholds["edge_threshold"]
            endpoint_t = thresholds["endpoint_threshold"]
            # Color each draw by whether it passes both edge conditions.
            passed = (x >= edge_t) & (y >= endpoint_t)
            ax.scatter(x[~passed], y[~passed], s=10, alpha=0.25, label="Fails at least one condition",)
            ax.scatter(x[passed], y[passed], s=12, alpha=0.6, label="Passes both",)
            ax.axvline(edge_t, linestyle="--", linewidth=2, label=f"Edge threshold = {edge_t:.2f}")
            ax.axhline(endpoint_t, linestyle=":", linewidth=2, label=f"Endpoint threshold = {endpoint_t:.2f}")
            ax.set_title(f"Configuration {c}")
            ax.set_xlabel("Sampled edge score")
            ax.grid(alpha=0.2)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        axes[0].set_ylabel("Sampled endpoint score")
        axes[-1].legend(loc="upper right", fontsize=8)
        fig.suptitle("Random draws relative to edge-availability thresholds")
        fig.tight_layout()
        plt.show()

    @staticmethod
    def calculate_tensor_mean(distance, axis=2):
        valid = np.isfinite(distance)
        count = valid.sum(axis=axis)
        total = np.nansum(distance, axis=axis)
        return np.divide(total, count, out=np.full(total.shape, np.nan), where=count > 0,)

    def _configure_simulation_matrix(self):
        """Allocate feature and configuration matrices."""
        self.feature_matrix = np.full((self.feature_space, self.n_subgraphs, self.n_sim,), np.nan, dtype=float,)
        self.configuration_matrix = np.zeros(
            (self.n_nodes + self.n_edges, self.n_combinations, self.n_subgraphs, self.n_sim,), 
            dtype=np.int8,
            )

    def _sample_distribution(self, feature_name:str, params:np.ndarray, size:int, rng:np.random.Generator):
        """Sample a feature using its configured distribution."""
        distribution = self.feature_distributions[feature_name]
        if distribution is np.random.beta:
            return rng.beta(params[:, 0, None], params[:, 1, None], size=size,)
        if distribution is weibull_min:
            scale = params[:, 0, None]
            loc = params[:, 1, None]
            shape = params[:, 2, None]
            return weibull_min.rvs(c=shape, loc=loc, scale=scale, size=size, random_state=rng,)
        raise ValueError(f"Unsupported distribution for {feature_name}: {distribution}")
    
    def _configure_subgraph_features(self, subgraph:nx.DiGraph):
        """Sample node and edge features for one subgraph."""
        M = self.n_sim
        N = self.n_nodes
        E = self.n_edges
        features = np.full((N + 3 * E, M), np.nan)
        nodes = list(subgraph.nodes())
        edges = list(subgraph.edges())
        node_idx = np.array([self.node_index[n] for n in nodes])
        edge_idx = np.array([self.edge_index[e] for e in edges])
        # Node score: Beta
        node_params = np.asarray([self.node_params["node_score"][n] for n in nodes], dtype=float,)
        features[node_idx] = self._sample_distribution("node_score", node_params, (len(nodes), M), self.rng_node,)
        # Edge score: Beta
        edge_score_params = np.asarray([self.edge_params["edge_score"][e] for e in edges], dtype=float,)
        features[N + edge_idx] = self._sample_distribution("edge_score", edge_score_params, (len(edges), M), self.rng_edge_score,)
        # Edge cost: Weibull
        edge_cost_params = np.asarray([self.edge_params["edge_cost"][e] for e in edges], dtype=float,)
        features[N + E + edge_idx] = self._sample_distribution("edge_cost", edge_cost_params, (len(edges), M), self.rng_edge_cost,)
        # Endpoint score: select the higher-weight endpoint, then sample Beta.
        endpoint_params = np.asarray([self.edge_params["edge_endpoint_score"][e] for e in edges], dtype=float,)
        endpoint_weights = np.asarray([self.edge_params["edge_endpoint_weights"][e] for e in edges], dtype=float,)
        # Endpoint decision process
        alpha = endpoint_params[:, :, 0, None]
        beta = endpoint_params[:, :, 1, None]
        endpoint_draws = self.rng_endpoint_score.beta(alpha, beta, size=(len(edges), 2, M),)
        selected_endpoint = np.argmax(endpoint_weights, axis=1)
        # Allocate selected draws for endpoints
        selected_draws = endpoint_draws[np.arange(len(edges)), selected_endpoint, :,]
        features[N + 2 * E + edge_idx] = selected_draws
        return features

    def _configure_graph_matrix(self):
        """Sample subgraph features and evaluate threshold combinations."""
        N = self.n_nodes
        E = self.n_edges
        self._configure_simulation_matrix()
        node_thresholds = np.asarray([combination["node_threshold"] for combination in self.combinations])[:, None, None]
        edge_thresholds = np.asarray([combination["edge_threshold"] for combination in self.combinations])[:, None, None]
        endpoint_thresholds = np.asarray([combination["endpoint_threshold"] for combination in self.combinations])[:, None, None]
        # Configure graph matrix for each subgraph
        for subgraph_idx, subgraph in enumerate(self.subgraphs):
            features = self._configure_subgraph_features(subgraph)
            self.feature_matrix[:, subgraph_idx, :] = features
            # Get simulation slices
            node_scores = features[:N]
            edge_scores = features[N:N + E]
            endpoint_scores = features[N + 2 * E:N + 3 * E]
            # Get data to populate the graph matrix for analysis
            node_available = (node_scores[None, :, :] >= node_thresholds)
            edge_available = ((edge_scores[None, :, :] >= edge_thresholds) & (endpoint_scores[None, :, :] >= endpoint_thresholds))
            self.configuration_matrix[:N, :, subgraph_idx, :] = (node_available.transpose(1, 0, 2))
            self.configuration_matrix[N:, :, subgraph_idx, :] = (edge_available.transpose(1, 0, 2))
        return self.configuration_matrix

    def _initialize_path_results(self, source_sink_pairs:Dict[int, List[tuple]]):
        """Allocate dense result arrays and create pair-index mappings."""
        def case_index(case):
            return int(case.rsplit("_", 1)[1]) if isinstance(case, str) else int(case)
        self.path_pairs = [
            (case_index(case), source, sink) for case, pairs in source_sink_pairs.items() for source, sink in pairs
            ]
        if len(set(self.path_pairs)) != len(self.path_pairs):
            raise ValueError("Duplicate case/source/sink entries found.")
        self.path_pair_index = {pair: i for i, pair in enumerate(self.path_pairs)}
        shape = (len(self.path_pairs), self.n_combinations, self.n_sim,)
        self.reachability = np.zeros(shape, dtype=np.int8)
        self.shortest_distance = np.full(shape, np.nan, dtype=np.float64)
        return self.reachability, self.shortest_distance        