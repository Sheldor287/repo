import os 
import numpy as np
import pandas as pd
import networkx as nx

class DependenceAnalysis:
    def __init__(self, graph:nx.DiGraph=None, node_probabilities:list=None, to_return=False):
        # Graph initialization
        self.graph = nx.DiGraph() if graph is None else graph
        if graph is None:
            self.edges = [(0,1), (1,3), (3,5), (0,2), (2,4), (4,5)] 
            self.graph.add_edges_from(self.edges)
        else:
            self.edges = list(self.graph.edges())  
        self.nodes = sorted(self.graph.nodes())
        self.n_nodes = len(self.nodes)
        # Simulation initialization 
        if graph is None and node_probabilities is None:
            self.probabilities = np.array([0.98, 0.90, 0.90, 0.90, 0.90, 0.98], dtype=float)
        elif graph is None and node_probabilities and len(node_probabilities) != 6:
            self.probabilities = np.array([0.98, 0.90, 0.90, 0.90, 0.90, 0.98], dtype=float)
        elif graph is not None and node_probabilities is None:
            arr = np.random.uniform(0.85, 0.95, size=self.nodes-2)
            arr = np.insert(arr, 0, .98)
            arr = np.insert(arr, len(arr), 0.98)
            self.probabilities = arr
        elif graph is not None and node_probabilities is not None:
            if len(node_probabilities) != len(graph.nodes()):
                raise Exception('Node probabilties not assigned for all nodes')
            self.probabilities = node_probabilities

        self.n_sim, self.seed, self.q_cause, self.q_prox = 100000, 123, 0.08, 0.1
        self.env_probs = (0.98, 0.7)
        self.rng = np.random.default_rng(self.seed)
        self.none = None

        self.to_return = True if to_return is True else False
        self.MODELS = {
            'independent': self.independent_model,
            'common_cause': self.common_cause_model,
            'functional_dependence': self.functional_dependence_model,
            'shared_resource': self.shared_resource_model,
            'shared_environment': self.shared_environment_model,
            'proximity': self.proximity_model
        }

    def independent_model(self, rng=None):
        rng = self.rng if rng is None else rng
        return rng.random((self.n_sim, len(self.nodes))) < self.probabilities

    def common_cause_model(self, rng=None, q=None):
        """
        With probability q, a shared system failure disables all intermediate nodes. 
        Conditional probabilities are calibrated to retain marginal .90.
        """
        rng = self.rng if rng is None else rng
        q = self.q_cause if q is None else q
        p_cond = self.probabilities[1] / (1 - q)
        X = np.empty((self.n_sim, len(self.nodes)), dtype=bool)
        X[:, 0] = rng.random(self.n_sim) < self.probabilities[0]
        X[:, 5] = rng.random(self.n_sim) < self.probabilities[5]
        shock = rng.random(self.n_sim) < q
        X[:, 1:5] = rng.random((self.n_sim, 4)) < p_cond
        X[shock, 1:5] = False
        self.X_common_cause = X
        return X

    def functional_dependence_model(self, rng=None):
        """Node 3 requires node 1; node 4 requires node 2."""
        rng = self.rng if rng is None else rng
        X = rng.random((self.n_sim, self.n_nodes)) < self.probabilities
        X[:, 3] &= X[:, 1]
        X[:, 4] &= X[:, 2]
        self.X_functional_dependence = X
        return X

    def shared_resource_model(self, rng=None):
        """Nodes 1 and 2 compete for a resource with capacity one."""
        rng = self.rng if rng is None else rng
        X = rng.random((self.n_sim, self.n_nodes)) < self.probabilities
        both = X[:, 1] & X[:, 2]
        choose_left = rng.random(self.n_sim) < 0.5
        X[both & choose_left, 2] = False
        X[both & ~choose_left, 1] = False
        self.X_shared_resource = X
        return X

    def shared_environment_model(self, rng=None, env_probs=None):
        """
        A shared good/bad environmental state changes intermediate-node conditional probabilities. 
        Conditional draws are independent; shared environment creates marginal dependence. 
        Marginal p=.90.
        """
        rng = self.rng if rng is None else rng
        p_good, p_bad = self.env_probs if env_probs is None else env_probs
        prob_good = (self.probabilities[1] - p_bad)/(p_good - p_bad)
        good = rng.random(self.n_sim) < prob_good
        X = np.empty((self.n_sim, len(self.nodes)), dtype=bool)
        X[:, 0] = rng.random(self.n_sim) < self.probabilities[0]
        X[:, 5] = rng.random(self.n_sim) < self.probabilities[5]
        conditional_p = np.where(good, p_good, p_bad)
        X[:, 1:5] = rng.random((self.n_sim, 4)) < conditional_p[:, None]
        self.X_shared_environment = X
        return X

    def proximity_model(self, rng=None, q=None):
        """Nodes 1 and 3 share one zone; nodes 2 and 4 share another."""
        rng = self.rng if rng is None else rng
        q = self.q_prox if q is None else q
        p_clear = self.probabilities[1] / (1 - q)
        X = np.empty((self.n_sim, self.n_nodes), dtype=bool)
        X[:, 0] = rng.random(self.n_sim) < self.probabilities[0]
        X[:, 5] = rng.random(self.n_sim) < self.probabilities[5]
        X[:, 1:5] = (rng.random((self.n_sim, 4)) < p_clear)
        # Disruption zones: left (1,3) and right (2,4)
        left_disruption = rng.random(self.n_sim) < q
        right_disruption = rng.random(self.n_sim) < q
        X[left_disruption, 1] = False
        X[left_disruption, 3] = False
        X[right_disruption, 2] = False
        X[right_disruption, 4] = False
        self.X_proximity = X
        return X

    def metrics(self, X):
        route_a = X[:, 0] & X[:, 1] & X[:, 3] & X[:, 5]
        route_b = X[:, 0] & X[:, 2] & X[:, 4] & X[:, 5]

        network = route_a | route_b

        return {
            'network_traversable': network.mean(),
            'route_a_traversable': route_a.mean(),
            'route_b_traversable': route_b.mean(),
            'both_routes_fail': (~route_a & ~route_b).mean(),
            'active_nodes': X.sum(axis=1).mean(),
            **{f'node_{i}_active': X[:, i].mean() for i in range(self.n_nodes)}
        }

    def run_analysis(self, q_prox=None, q_cause=None, env_params=None):
        rows = []
        for i, (name, model) in enumerate(self.MODELS.items()):
            rng = np.random.default_rng(self.seed + i)
            if name == 'proximity':
                X = model(rng, q=q_prox)
            elif name == 'common_cause':
                X = model(rng, q=q_cause)
            elif name == 'shared_environment':
                X = model(rng, env_probs=env_params)
            else:
                X = model(rng)
            rows.append({'model': name, **self.metrics(X)})

        results = pd.DataFrame(rows)
        baseline = results.loc[results['model'] == 'independent', 'network_traversable'].iloc[0]
        results['baseline_delta'] = results['network_traversable'] - baseline
        results.to_csv('dependence_analysis_results.csv', index=False) 
        if self.to_return:
            return results 

    def run_probability_sensativity(self, p_array=None, var=0.01, output_file='prob_sweep.csv', rows=[]):
        """ Nodes 0,5 retain their probabilities, all other nodes change """
        # Initialize probability sweep
        original_probabilities = self.probabilities.copy()
        return_status = self.to_return
        if p_array is None:
            probability_values = np.linspace(0.80, 0.99, 25)
        for p in probability_values:
            # Create small variance for the nodes centered around the test target
            self.probabilities[1:5] = self.rng.normal(p, var, size=4)
            while any(x > 1 for x in self.probabilities):
                var /= 10
                self.probabilties[1:5] = self.rng.normal(p, var, size=4)
            # Get/record results
            self.to_return = True
            results = self.run_analysis()
            results['intermediate_probability'] = p
            rows.append(results)
        # Combine results and replace state
        results = pd.concat(rows, ignore_index=True)
        results = results.sort_values(by=['model', 'intermediate_probability'])
        results.to_csv(output_file, index=False)
        self.probabilities[:] = original_probabilities
        self.to_return = return_status
        if self.to_return:
            return results 

    def run_parameter_sensitivity(self, env_probs=None, cause_probs=None, prox_probs=None, output_file='param_sweep.csv', rows=[]):
        """Runs a parameter sensitivity analysis of dependence-cause factors."""
        env_probs = env_probs or [(0.98 - x / 95, 0.8 - y / 25) for x in range(4) for y in range(3)]
        cause_probs = cause_probs if cause_probs is not None else np.linspace(0.01, 0.15, 11)
        prox_probs = prox_probs if prox_probs is not None else np.linspace(0.015, 0.1, 11)
        # Define sweeps with: (attribute_name, iterable_values, label_name)
        sweeps = [('env_probs', env_probs, 'shared_environment'), ('q_cause', cause_probs, 'common_cause'), ('q_prox', prox_probs, 'proximity')]
        original_state = {attr: getattr(self, attr) for attr, _, _ in sweeps}
        return_status = getattr(self, 'to_return', True)
        self.to_return = True
        # Run and record the standard/baseline sweep explicitly first
        standard_res = self.run_analysis()
        standard_res['parameter_changed'] = 'standard'
        param_map = {'shared_environment': self.env_probs, 'common_cause': self.q_cause, 'proximity': self.q_prox}
        standard_res['param_value'] = standard_res['model'].map(param_map)
        rows.append(standard_res)
        # Run the dynamic parameter sweeps
        for attr, values, label in sweeps:
            for val in values:
                setattr(self, attr, val)
                res = self.run_analysis()
                res['parameter_changed'] = label
                res['param_value'] = str(val) if isinstance(val, tuple) else val
                # Filter for independent baseline + the active dependence model row
                res = res[res['model']==label]
                rows.append(res)
        for attr, val in original_state.items():
            setattr(self, attr, val)
            self.to_return = return_status
        # Record
        results = pd.concat(rows, ignore_index=True)
        results = results.sort_values(by=['parameter_changed', 'baseline_delta'])
        results.to_csv(output_file, index=False)
        if self.to_return:
            return results
        
if __name__ == '__main__':
    da = DependenceAnalysis()
    da.run_analysis()
    da.run_probability_sensativity()
    da.run_parameter_sensitivity()
    print(f'Notional Analysis Demo Saved to Current Working Directory: {os.getcwd()}\n'
          f'Standard Analysis: dependence_analysis_results.csv\n',
          f'Probability Sensativity Analysis: prob_sweep.csv\n',
          f'Parameter Sensativity Analysis: param_sweep.csv'
          )

