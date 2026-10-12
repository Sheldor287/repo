import itertools
import numpy as np
from scipy.stats import weibull_min

FEATURE_DISTRIBUTIONS = {
    "node_score": np.random.beta,
    "edge_score": np.random.beta,
    "edge_cost": weibull_min,
}

THRESHOLD_STATES = {
    "node_threshold": np.linspace(0.1, 0.9, 5),
    "edge_threshold": np.linspace(0.5, 0.9, 5),
    "endpoint_threshold": np.linspace(0.1, 0.8, 5),
}

THRESHOLD_RULES = {
    "rule1": lambda node, edge: (node >= 0.5 and edge <= 0.7),
    "rule2": lambda node, endpoint: (node < 0.5 and endpoint >= 0.8),
}

PARAMETER_ATTRIBUTES = {
    "node_score": "node_params1",
    "edge_score": "edge_params1",
    "edge_cost": "edge_params2",
    "edge_endpoint_score": "edge_params3",
    "edge_endpoint_weights": "edge_params4",
}

SOURCE_SINK_PAIRS = {
    0: [(0, 13), (0, 17)],
    1: [(0, 4), (0, 7)],
    2: [(0, 29)],
}

def valid_combinations(states, rules):
    names = list(states)
    candidates = itertools.product(*(states[name] for name in names))
    combinations = []
    for values in candidates:
        thresholds = dict(zip(names, values))
        if (
            not rules["rule1"](thresholds["node_threshold"], thresholds["edge_threshold"],)
            and not rules["rule2"](thresholds["node_threshold"], thresholds["endpoint_threshold"],)
        ):
            combinations.append(thresholds)
    return combinations
    

sim_kwargs={
    'state_params': THRESHOLD_STATES, 
    'sim_config': FEATURE_DISTRIBUTIONS, 
    'param_names': PARAMETER_ATTRIBUTES,
    'combinations': valid_combinations(THRESHOLD_STATES, THRESHOLD_RULES),
    'seed': 123,
    'n_sim': 1000}

"""
README: 

Constants is meant to correct map a concrete problem set to the abstract model structure.
Refactoring will include:

1) from simulation import Sim 
    Sim.__configure_graph_matrix
    directly depends on the size of the dictionary RANDOM_PARAM_STATES:

            # Thresholds: shape (C, 1, 1).
            tau_node = np.asarray([comb[0] for comb in self.combinations], dtype=float)[:, None, None]
            tau_edge = np.asarray([comb[1] for comb in self.combinations], dtype=float)[:, None, None]
            tau_edge2 = np.asarray([comb[2] for comb in self.combinations], dtype=float)[:, None, None]
"""