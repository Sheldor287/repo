from collections import defaultdict
from pyomo import environ as pyo
import matplotlib.pyplot as plt
from tqdm import trange
import networkx as nx
import pandas as pd
import numpy as np
import inspect
import re

from sklearn.metrics import r2_score, mean_absolute_error, accuracy_score
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

class Analysis:
    """
    Analysis layer for Solver results and stochastic network simulations.

    Supports:
        - max_flow
        - min_cut
        - node_interdiction

    The class is intentionally separated from LP and Solver:
        LP          -> constructs optimization model
        Solver   -> solves model and standardizes results
        Analysis -> interprets/analyzes those results
    """
    FORMULATION_INFO = {
        "max_flow": { "value_name": "flow", "performance_direction": "higher", "failure_condition": "zero", },
        "min_cut": { "value_name": "cut_capacity", "performance_direction": "higher", "failure_condition": "zero", },
        "node_interdiction": { "value_name": "interdicted_cut_capacity", "performance_direction": "lower", "failure_condition": "zero", },
    }

    def __init__(self, solver):
        self.solver = solver
        self.g = solver.g
        self.model = solver.model
        self.model_type = solver.model_type
        self.results = solver.results
        # Statistics
        self.node_results = self.results.get("node_results", {})
        self.edge_results = self.results.get("edge_results", {})
        self.metrics = self.results.get("metrics", {})
        self.problem = self.results.get("problem", {})
        self.solver_results = self.results.get("solver", {})
        # Simulation attributes
        self.nodes = None
        self.edges = None
        self.node_p = None
        self.edge_p = None

    # General solver results
    def analysis_step(category, description=""):
        def decorator(func):
            func._analysis_category = category
            func._analysis_description = description
            return func
        return decorator

    def ml(self):
        return GraphML(self, df=self.stochastic_analysis(n_sim=50,seed=123,))

    @analysis_step("Solution", "General solution information")
    def summary(self):
        """Return a formulation-independent summary of the solution"""
        return {
            "model_type": self.model_type,
            "objective_value": self.problem.get("objective_value"),
            "status": self.solver_results.get("status"),
            "termination_condition":self.solver_results.get("termination_condition"),
            "cut_capacity":self.metrics.get("cut_capacity"),
            "capacity_removed":self.metrics.get("capacity_removed"),
            "interdiction_cost":self.metrics.get("interdiction_cost"),
            "budget":self.metrics.get("budget"),
        }
    
    @analysis_step("Solution", "Optimization objective value")
    def get_objective_value(self):
        return self.problem.get("objective_value")

    # Node / edge access
    @analysis_step("Get Data", "Node Results")
    def get_node_results(self):
        return self.node_results
    
    @analysis_step("Get Data", "Edge Results")
    def get_edge_results(self):
        return self.edge_results

    @analysis_step("Get Data", "Solver Metrics")
    def get_metrics(self):
        return self.metrics

    # Cut analysis
    @analysis_step("Cut Analysis", "Edges belonging to the minimum cut")
    def get_cut_edges(self):
        """Return edges identified as belonging to the minimum cut. Works for both min_cut and node_interdiction results."""
        return [edge for edge, data in self.edge_results.items() if data.get("in_cut", False)]

    @analysis_step("Cut Analysis", "Edges belonging to the interdicted cut")
    def get_interdicted_cut_edges(self):
        """Return edges actually contributing to the interdicted cut. Returns an empty list for formulations without interdiction."""
        return [edge for edge, data in self.edge_results.items() if data.get("in_interdicted_cut", False)]

    @analysis_step("Cut Analysis", "Returns the maximum flow left on the network")
    def get_cut_capacity(self):
        return self.metrics.get("cut_capacity")

    @analysis_step("Cut Analysis", "Returns the maximum flow destroyed by the interdiction")
    def get_capacity_removed(self):
        return self.metrics.get("capacity_removed", 0)

    # Interdiction analysis
    @analysis_step("Interdiction", "Nodes selected for interdiction")
    def get_interdicted_nodes(self):
        """Return nodes selected by the interdiction formulation."""
        return [node for node, data in self.node_results.items() if data.get("interdicted", False)]
    
    @analysis_step("Interdiction", "Price of node interdiction")
    def get_interdiction_cost(self):
        return self.metrics.get("interdiction_cost", 0)
    
    @analysis_step("Interdiction", "How much capacity is lost per unit cost")
    def get_interdiction_efficiency(self):
        """Capacity removed per unit interdiction cost."""
        cost = self.get_interdiction_cost()
        removed = self.get_capacity_removed()
        if cost is None or cost <= 0:
            return None
        return removed / cost

    ##################################
    ####### Simulation Helpers #######
    ##################################

    # Component identification
    @staticmethod
    def _get_component_columns(df):
        """Identify node and edge state columns in a simulation dataframe."""
        node_cols = [c for c in df.columns if re.match(r"^node_.+$", c)]
        edge_cols = [c for c in df.columns if re.match(r"^edge_\(.+\)$", c)]
        return node_cols, edge_cols

    # Stochastic simulation preprocessing
    def _preprocess_network_simulation(self):
        self.nodes = [n for n in self.g.nodes() if not self.g.nodes[n].get("artificial", False)]
        self.edges = [(u, v) for u, v in self.g.edges() if not self.g.edges[u, v].get("artificial", False)]
        self.node_p = np.array([self.g.nodes[n].get("probability1", 1) for n in self.nodes])
        self.edge_p = np.array([self.g.edges[u, v].get("probability", 1)for u, v in self.edges])

    def _sample_states(self, rng):
        """Sample operational states for nodes and edges"""
        node_state = rng.binomial(1, self.node_p)
        edge_state = rng.binomial(1, self.edge_p)
        return node_state, edge_state

    #######################################
    ####### Monte Carlo Simulations #######
    #######################################

    @analysis_step("Monte Carlo", "Main Optimization Solver")
    def stochastic_analysis(self,n_sim=1000,seed=123,solver_str="appsi_highs",):
        """
        Perform stochastic analysis using the current LP formulation.

        The graph structure and Pyomo model are retained. Only mutable
        node_state and edge_state parameters are changed between runs.
        The interpretation of the resulting objective depends on the formulation:

            max_flow: realized maximum flow
            min_cut: realized minimum cut
            node_interdiction: realized interdicted minimum cut
        """
        if not hasattr(self.model, "node_state"):
            raise AttributeError("The current model does not contain mutable node_state.")
        if not hasattr(self.model, "edge_state"):
            raise AttributeError("The current model does not contain mutable edge_state.")
        self._preprocess_network_simulation()
        rng = np.random.default_rng(seed)
        pyo_solver = pyo.SolverFactory(solver_str)
        results = []
        for i in trange(n_sim):
            node_state, edge_state = self._sample_states(rng)
            for n, state in zip(self.nodes, node_state):
                self.model.node_state[n] = int(state)
            for (u, v), state in zip(self.edges, edge_state):
                self.model.edge_state[u, v] = int(state)
            result = pyo_solver.solve(self.model)
            results.append(self._process_simulation_result(result,node_state,edge_state,i,))
        return pd.DataFrame(results)

    def _process_simulation_result(self,result,node_state,edge_state,i,):
        """Convert one stochastic optimization result into a dataframe row"""
        objective = pyo.value(self.model.obj)
        node_operational = int(node_state.sum())
        node_failed = len(node_state) - node_operational
        edge_operational = int(edge_state.sum())
        edge_failed = len(edge_state) - edge_operational
        row = {
            "sim_number": i,
            "objective": objective,
            "node_operational": node_operational,
            "node_failed": node_failed,
            "edge_operational": edge_operational,
            "edge_failed": edge_failed,
            "node_opr_ratio":node_operational / len(self.nodes),
            "edge_opr_ratio":edge_operational / len(self.edges),
            "termination_condition":str(result.solver.termination_condition),
        }
        ## Formulation-specific aliases
        if self.model_type == "max_flow":
            row["flow"] = objective
            row["flow_failure_indicator"] = int(objective == 0)
        elif self.model_type == "min_cut":
            row["cut_capacity"] = objective
            row["cut_failure_indicator"] = int(objective == 0)
        elif self.model_type == "node_interdiction":
            row["interdicted_cut_capacity"] = objective
            row["interdiction_failure_indicator"] = int(objective == 0)
        ## Component states
        for n, state in zip(self.nodes, node_state):
            row[f"node_{n}"] = int(state)
        for (u, v), state in zip(self.edges, edge_state):
            row[f"edge_({u},{v})"] = int(state)
        return row

    # Reliability analysis
    @staticmethod
    @analysis_step("Reliability", "P(Y >= threshold)")
    def reliability(df,threshold,y_column="objective",):
        return (df[y_column] >= threshold).mean()

    @staticmethod
    @analysis_step("Reliability", "P(Y < threshold)")
    def failure_probability(df,threshold,y_column="objective",):
        return (df[y_column] < threshold).mean()

    @staticmethod
    @analysis_step("Reliability", "Construct the empirical reliability curve: R(q) = P(Y >= q)")
    def reliability_curve(df, y_column="objective",):
        values = np.sort(df[y_column].dropna().unique())
        return pd.DataFrame({
            "requirement": values, "reliability": [(df[y_column] >= q).mean()for q in values],
        })

    @staticmethod
    @analysis_step("Reliability", "Summarize the empirical distribution of network performance")
    def performance_distribution(df,y_column="objective",threshold=None):
        values = df[y_column].dropna()
        if values.empty:
            return {}
        return {
            "mean": values.mean(),
            "median": values.median(),
            "std": values.std(),
            "variance": values.var(),
            "min": values.min(),
            "max": values.max(),
            "q05": values.quantile(0.05),
            "q10": values.quantile(0.10),
            "q25": values.quantile(0.25),
            "q50": values.quantile(0.50),
            "q75": values.quantile(0.75),
            "q90": values.quantile(0.90),
            "q95": values.quantile(0.95),
            "zero_probability": (values == 0).mean(),
            "reliability_threshold": threshold,
            "reliability": (values >= threshold).mean() if threshold is not None else None,
            "probability_of_failure": (values < threshold).mean() if threshold is not None else None,
        }

    @analysis_step("Reliability", "The meta-collection of stochastic network performance")
    def performance_summary(self,df,y_column="objective",threshold=None,):
        summary = self.performance_distribution(df,y_column=y_column,)
        if threshold is not None:
            summary["reliability"] = (self.reliability(df,threshold,y_column,))
            summary["failure_probability"] = (self.failure_probability(df,threshold,y_column,))
            summary["expected_shortfall"] = (self.expected_shortfall(df,threshold,y_column,))
        return summary

    @staticmethod
    @analysis_step("Reliability", "Estimate the expected network performance conditional on performance being below a threshold.")    
    def expected_shortfall(df,threshold,y_column="objective",):
        values = df[y_column].dropna()
        tail = values[values < threshold]
        if tail.empty:
            return np.nan
        return tail.mean()

    @staticmethod
    @analysis_step("Reliability", "Resilience curves capturing expected performance as a function of component failures")   
    def resilience_curve(df,y_column="objective",failure_column="node_failed",baseline=None,):
        """
        Estimate expected performance as a function of component failures.
        For each number of failed components k: E[Y | failures = k]
        If baseline is supplied, also calculate: E[Y | failures = k] / baseline.

        USABLE for both nodes and edges.
        """
        data = df[[y_column, failure_column]].dropna()
        if data.empty:
            return pd.DataFrame()
        if baseline is None:
            baseline = data[y_column].max()
        curve = (data.groupby(failure_column)[y_column].agg(mean="mean",median="median",std="std",count="count",).reset_index())
        curve["relative_performance"] = (curve["mean"] / baseline if baseline and baseline != 0 else np.nan)
        return curve

    # Component influence
    @staticmethod
    def _get_influence_logic(df,component_columns,y_column="objective",):
        """Calculate conditional performance associated with component state."""
        results = []
        for component in component_columns:
            operational = df[component] == 1
            failed = df[component] == 0
            value_operational = (df.loc[operational, y_column].mean() if operational.any() else np.nan)
            value_failed = (df.loc[failed, y_column].mean() if failed.any() else np.nan)
            difference = (value_operational - value_failed if not np.isnan(value_failed) else np.nan)
            relative_difference = (difference / value_operational if (not np.isnan(difference) and value_operational != 0) else np.nan)
            results.append({
                "component": component,
                "value_if_operational": value_operational,
                "value_if_failed": value_failed,
                "value_difference": difference,
                "relative_impact": relative_difference,
                "n_operational": operational.sum(),
                "n_failed": failed.sum(),
                "observed_performance_rate": operational.mean(),
            })
        return (pd.DataFrame(results).sort_values("value_difference",ascending=False,).reset_index(drop=True))

    @analysis_step("Reliability", "Return separate node and edge component influence tables.")   
    def get_component_influence(self,df,y_column="objective",):
        node_cols, edge_cols = self._get_component_columns(df)
        node_results = self._get_influence_logic(df,node_cols,y_column,)
        edge_results = self._get_influence_logic(df,edge_cols,y_column,)
        return node_results, edge_results

    # Component reliability importance
    @analysis_step("Compinent Reliability", "R_i = P(Y >= q | X_i = 1) - P(Y >= q | X_i = 0).")   
    def get_component_reliability(self,df,threshold,y_column="objective",):
        """Calculate component-level reliability impact. R_i = P(Y >= q | X_i = 1) - P(Y >= q | X_i = 0)"""
        node_cols, edge_cols = self._get_component_columns(df)
        results = []
        for component in node_cols + edge_cols:
            operational = df[component] == 1
            failed = df[component] == 0
            reliability_operational = ((df.loc[operational, y_column] >= threshold).mean() if operational.any() else np.nan)
            reliability_failed = ((df.loc[failed, y_column] >= threshold).mean() if failed.any() else np.nan)
            impact = (reliability_operational - reliability_failed if not np.isnan(reliability_failed) else np.nan)
            results.append({
                "component": component,
                "component_type": "node" if component in node_cols else "edge",
                "reliability_if_operational": reliability_operational,
                "reliability_if_failed": reliability_failed,
                "reliability_impact": impact,
                "n_operational": operational.sum(),
                "n_failed": failed.sum(),
                "observed_failure_rate": failed.mean(),
            })
        return (pd.DataFrame(results).sort_values("reliability_impact",ascending=False,).reset_index(drop=True))

    # Plotting
    @analysis_step("Plotting", "R(q) = P(Y >= q)")   
    def plot_reliability_curve(self,df,y_column="objective",threshold=None,ax=None,):
        """Plot: R(q) = P(Y >= q)"""
        if ax is None:
            _, ax = plt.subplots(figsize=(8, 5))
        curve = self.reliability_curve(df,y_column=y_column,)
        ax.step(curve["requirement"],curve["reliability"],where="post",)
        if threshold is not None:
            ax.axvline(threshold,linestyle="--",label=f"Required value of Flow: {threshold}",)
            ax.legend()
        ax.set_xlabel("Required Value of Flow")
        ax.set_ylabel("Reliability")
        ax.set_title("Network Reliability Curve",weight="bold",)
        ax.set_ylim(0, 1.02)
        ax.grid(True, alpha=0.3)
        return ax

    @analysis_step("Plotting", "Plot expected network performance as components fail.")       
    def plot_resilience_curve(self,df,y_column="objective",failure_column="node_failed",baseline=None,relative=True,ax=None,):
        if ax is None:
            _, ax = plt.subplots(figsize=(8, 5))
        curve = self.resilience_curve(df,y_column=y_column,failure_column=failure_column,baseline=baseline,)
        if curve.empty:
            return ax
        y_column = ("relative_performance"if relative else "mean")
        ax.plot(curve[failure_column],curve[y_column],marker="o",)
        ax.set_xlabel("Number of Failed " + ("Nodes" if "node" in failure_column else "Edges"))
        ax.set_ylabel("Relative Performance" if relative else "Expected Performance")
        ax.set_title("Network Resilience Curve", weight="bold",)
        ax.grid(True, alpha=0.3)
        if relative:
            ax.set_ylim(bottom=0)
        return ax

    @staticmethod
    @analysis_step("Plotting", "Plot the components having the greatest reliability impact.")   
    def plot_component_reliability(reliability_df,top_n=15,ax=None,):
        if ax is None:
            _, ax = plt.subplots(figsize=(9, 6))
        data = reliability_df.head(top_n).iloc[::-1]
        ax.barh(data["component"],data["reliability_impact"],)
        ax.set_xlabel("Reliability Impact")
        ax.set_ylabel("Component")
        ax.set_title("Component Reliability Importance",weight="bold",)
        ax.grid(True,axis="x",alpha=0.3,)
        return ax

    @classmethod
    def show_workflow(cls):
        categories = defaultdict(list)
        # Inspect methods defined on Analysis
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            category = getattr(method, "_analysis_category", None)
            if category is None:
                continue
            description = getattr(method,"_analysis_description","")
            categories[category].append((name, description))
        print(f"\n{cls.__name__} — Analysis Workflow")
        print("│")
        category_items = list(categories.items())
        for i, (category, methods) in enumerate(category_items):
            is_last_category = i == len(category_items) - 1
            category_prefix = "|--> " if is_last_category else "|--> "
            print(f"{category_prefix}{category}")
            method_prefix = "    " if is_last_category else "|   "
            for j, (name, description) in enumerate(methods):
                is_last_method = j == len(methods) - 1
                branch = "|--> " if is_last_method else "|--> "
                print(f"{method_prefix}{branch}{name}() — {description}" if description else "")
        print()

class GraphMetrics:
    """
    Graph-theoretic analysis layer.

    GraphML consumes:
        - Analysis for solved/stochastic network behavior
        - NetworkX graph structure for graph-theoretic features
        - stochastic DataFrame for ML-based performance analysis

    Capabilities:
        1. Clustering & other network metrics
        2. Special analysis + (1) --> ML data-table
        2. Random forest / permutation importance
        3. Spectral metrics
        4. Relationship between graph structure and optimization performance
    """
    def __init__( self, analysis:Analysis=None,):
        self.analysis = analysis
        if analysis is not None:
            self.solver = analysis.solver
            self.g = analysis.g
            self.results = analysis.results
            self.node_results = analysis.node_results
            self.edge_results = analysis.edge_results
            self.metrics = analysis.metrics
        else:
            self.solver = None
            self.g = None
            self.results = {}
            self.node_results = {}
            self.edge_results = {}
            self.metrics = {}
            
    # Validation
    def _require_graph(self):
        if self.g is None:
            raise ValueError("GraphML requires an Analysis object.")
        
    # Graph information
    def graph_info(self):
        """Return basic structural information about the graph."""
        self._require_graph()
        return {
            "nodes": self.g.number_of_nodes(),
            "edges": self.g.number_of_edges(),
            "density": nx.density(self.g),
            "directed": self.g.is_directed(),
            "weighted": nx.is_weighted(self.g),
            "connected": (nx.is_weakly_connected(self.g) if self.g.is_directed() else nx.is_connected(self.g)),
        }
    
    # Combined structural features --> Main ML df
    def node_features(self):
        """Return a single node-level structural feature table: Primary ML Object"""
        degree = self.degree_metrics()
        centrality = self.centrality_metrics()
        clustering = self.clustering_metrics()
        spectral = self.spectral_node_features()
        community = self.community_detection()
        df = (
            degree.merge(centrality, on="node")
            .merge(clustering, on="node")
            .merge(spectral, on="node")
            .merge(community, on='node')
            .reset_index(drop=True)
        )
        return df
    
    # Degree metrics
    def degree_metrics(self):
        """Calculate node-level degree-based structural metrics"""
        self._require_graph()
        rows = []
        for node in self.g.nodes:
            if self.g.is_directed():
                in_degree = self.g.in_degree(node)
                out_degree = self.g.out_degree(node)
            else:
                in_degree = self.g.degree(node)
                out_degree = self.g.degree(node)
            rows.append({"node": node, "degree": self.g.degree(node), "in_degree": in_degree, "out_degree": out_degree,})
        return pd.DataFrame(rows)
    
    # Centrality metrics
    def centrality_metrics(self, max_iter=1000):
        """Calculate common node-centrality measures"""
        self._require_graph()
        degree = nx.degree_centrality(self.g)
        betweenness = nx.betweenness_centrality(self.g)
        closeness = nx.closeness_centrality(self.g)
        try:
            eigenvector = nx.eigenvector_centrality(self.g, max_iter=max_iter)
        except nx.PowerIterationFailedConvergence:
            eigenvector = {node: np.nan for node in self.g.nodes}
        rows = []
        for node in self.g.nodes:
            rows.append({
                "node": node,
                "degree_centrality": degree[node],
                "betweenness_centrality": betweenness[node],
                "closeness_centrality": closeness[node],
                "eigenvector_centrality": eigenvector[node],
            })
        return pd.DataFrame(rows)

    # Local clustering
    def clustering_metrics(self):
        """Calculate local clustering coefficients"""
        self._require_graph()
        clustering = nx.clustering(self.g)
        return pd.DataFrame(
            [{ "node": node, "clustering_coefficient": value,} for node, value in clustering.items()]
        )
    
    # Spectral metrics
    def spectral_metrics(self):
        """
        Calculate graph-level spectral metrics.

        adjacency_spectral_radius: Largest absolute eigenvalue of the adjacency matrix.
            Measures maximum propagation potential across a network.
            Higher values --> Faster spreading 

        adjacency_largest_eigenvalue: Largest real eigenvalue of the adjacency matrix.
            Is a measurement of overall density and how large the "hubs" are. 
            It tracks the size of the dominate flow over a set of commonly-used paths. 

        laplacian_algebraic_connectivity (Fiedler Value)): Second-smallest Laplacian eigenvalue.
            Quantifies how tightly connected the graph is as a single unit.
            0: G is not connected; The higher, the more difficult it is to disconnect  

        laplacian_spectral_gap: Difference between the two smallest Laplacian eigenvalues.
            This measures bottleneck potential. A large gap --> the absence of weak points

        laplacian_largest_eigenvalue: Largest Laplacian eigenvalue.
            The larger the eigenvalue, the more "bipartite" the graph is. 
            Bipartite = Seperatable into two clean parts that connect over the middle. 
        """

        self._require_graph()

        # Adjacency matrix
        A = nx.to_numpy_array(self.g)
        adjacency_eigenvalues = np.linalg.eigvals(A)
        adjacency_eigenvalues = np.real_if_close(adjacency_eigenvalues)
        adjacency_eigenvalues = np.real(adjacency_eigenvalues)

        # Laplacian
        if self.g.is_directed():
            # Use the underlying undirected topology for the standard Laplacian.
            G_lap = self.g.to_undirected()
        else:
            G_lap = self.g
        L = nx.laplacian_matrix(G_lap).toarray()
        laplacian_eigenvalues = np.linalg.eigvalsh(L)
        laplacian_eigenvalues = np.sort(np.real(laplacian_eigenvalues))

        # Algebraic connectivity
        if len(laplacian_eigenvalues) >= 2:
            algebraic_connectivity = (laplacian_eigenvalues[1])
            spectral_gap = (laplacian_eigenvalues[1] - laplacian_eigenvalues[0])
        else:
            algebraic_connectivity = 0.0
            spectral_gap = 0.0

        # Fiedler vector
        if len(laplacian_eigenvalues) >= 2:
            eigenvalues, eigenvectors = np.linalg.eigh(L)
            fiedler_vector = eigenvectors[:, 1]
        else:
            fiedler_vector = np.array([0.0])

        # Results
        return {
            "adjacency_spectral_radius": np.max(np.abs(adjacency_eigenvalues)),
            "adjacency_largest_eigenvalue": np.max(adjacency_eigenvalues),
            "laplacian_algebraic_connectivity": algebraic_connectivity,
            "laplacian_spectral_gap": spectral_gap,
            "laplacian_largest_eigenvalue": laplacian_eigenvalues[-1],
            "adjacency_eigenvalues": adjacency_eigenvalues,
            "laplacian_eigenvalues": laplacian_eigenvalues,
            "fiedler_vector": fiedler_vector,
        }
    # Node features --> node_features
    def spectral_node_features(self):
        """ Return node-level spectral features """
        self._require_graph()
        if self.g.is_directed():
            G = self.g.to_undirected()
        else:
            G = self.g
        L = nx.laplacian_matrix(G).toarray()
        eigenvalues, eigenvectors = np.linalg.eigh(L)
        rows = []
        for i, node in enumerate(G.nodes):
            row = {"node": node, "fiedler_value": eigenvectors[i, 1] if len(eigenvalues) > 1 else 0.0,}
            # Include a few low-order spectral coordinates.
            for k in range(min(3, eigenvectors.shape[1])):
                row[f"spectral_coordinate_{k}"] = (eigenvectors[i, k])
            rows.append(row)
        return pd.DataFrame(rows)
    
    def community_detection(self):
        """Detect structural communities.
        Handles mixed-type node identifiers by temporarily relabeling
        nodes to integers. Original node identifiers are restored in
        the returned DataFrame.
        """
        self._require_graph()
        G = ( self.g.to_undirected() if self.g.is_directed() else self.g )
        # Temporarily relabel nodes with integers
        node_map = { node: i for i, node in enumerate(G.nodes()) }
        inverse_map = { i: node for node, i in node_map.items() }
        H = nx.relabel_nodes(G, node_map)
        # Community detection happens on H, NOT G
        communities = nx.community.greedy_modularity_communities(H)
        # Convert results back to original node identifiers
        rows = []
        for community_id, community in enumerate(communities):
            for numeric_node in community:
                original_node = inverse_map[numeric_node]
                rows.append({ "node": original_node, "community": community_id, "community_size": len(community), })
        return (pd.DataFrame(rows) .sort_values( ["community", "node"], key=lambda col: col.map(str) if col.name == "node" else col ) .reset_index(drop=True))

class GraphML(GraphMetrics, Analysis):

    def __init__(self, analysis: Analysis = None, df: pd.DataFrame = None,):
        super().__init__(analysis)
        # Stochastic results df
        self.df = df
        # Structural feature matrices
        self.node_X = self.node_features()
        self.edge_X = None
        # Simulation matrices
        self.simulation_X = None
        self.simulation_y = None
        # Component target matrices
        self.node_y = None
        self.edge_y = None
        # ML objects
        self.cluster_df = None
        self.rf_model = None
        self.rf_importance = None
        self.permutation_importance = None
        # Graph encoders
        self.graph_encoder, self.graph_decoder = self._numeric_node_map()

    # Validation
    def _require_data(self):
        if self.df is None:
            raise ValueError( "GraphML requires a stochastic simulation DataFrame." )
    def _require_features(self):
        if self.node_X is None:
            raise ValueError( "Node feature matrix has not been initialized." )

    def _numeric_node_map(self):
        """Create a numeric representation of node labels."""
        mapping = {}
        inverse = {}
        next_negative = -1
        for node in self.g.nodes():
            if isinstance(node, (int, np.integer)):
                new_node = node
            else:
                new_node = next_negative
                next_negative -= 1
            mapping[node] = new_node
            inverse[new_node] = node
        return mapping, inverse


    # Matrix construction
    def get_simulation_matrix( self, y_column="objective", ):
        """ 
        Construct the scenario/component ML matrix.
        X:
            rows = stochastic scenarios
            columns = node/edge operational states
        y:
            optimization result for each scenario
        """
        self._require_data()
        node_cols, edge_cols = self._get_component_columns(self.df)
        self.simulation_X = self.df[node_cols + edge_cols].copy()
        self.simulation_y = self.df[y_column].copy()
        return self.simulation_X, self.simulation_y

    def target_matrices(self, y_column="objective",):
        """Construct node-level optimization influence targets"""
        self._require_data()
        node_influence, edge_influence = (self.analysis.get_component_influence( self.df, y_column=y_column,))
        self.node_y = node_influence.copy()
        self.edge_y = edge_influence.copy()
        return self.node_y, self.edge_y

    # Clustering
    def cluster_nodes(self, n_clusters:int=3, method:str="kmeans", scale:bool=True, random_state:int=123,) -> pd.DataFrame:
        """
        Cluster nodes according to structural characteristics.
            n_clusters: Number of clusters.
            method: {"kmeans", "hierarchical"} Clustering algorithm.
            scale: bool --> Standardize structural features before clustering.
        Returns: A dataframe of node|cluster assignment
        """
        self._require_features()
        X = self.node_X.drop(columns=["node"]).copy()
        if scale:
            X_model = StandardScaler().fit_transform(X)
        else:
            X_model = X.to_numpy()
        if method == "kmeans":
            model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10,)
        elif method == "hierarchical":
            model = AgglomerativeClustering(n_clusters=n_clusters,)
        else:
            raise ValueError( "method must be 'kmeans' or 'hierarchical'." )
        labels = model.fit_predict(X_model)
        self.cluster_df = self.node_X[["node"]].copy()
        self.cluster_df["cluster"] = labels
        return self.cluster_df

    # Random Forest
    def fit_random_forest(self, classification:bool=False, test_size:float=0.2, random_state:int=123, n_estimators:int=300,) -> pd.DataFrame:
        """
        Fit a Random Forest to stochastic simulation outcomes.

        X = component operational states
        y = optimization outcome
        """
        if self.simulation_X is None:
            self.get_simulation_matrix()
        X = self.simulation_X
        y = self.simulation_y
        X_train, X_test, y_train, y_test = train_test_split( X, y, test_size=test_size, random_state=random_state, )
        if classification:
            model = RandomForestClassifier( n_estimators=n_estimators, random_state=random_state, n_jobs=-1, )
        else:
            model = RandomForestRegressor( n_estimators=n_estimators, random_state=random_state, n_jobs=-1, )
        model.fit(X_train, y_train)
        self.rf_model = model
        if classification:
            prediction = model.predict(X_test)
            self.rf_metrics = { "accuracy": accuracy_score( y_test, prediction, ) }
        else:
            prediction = model.predict(X_test)
            self.rf_metrics = {"r2": r2_score( y_test, prediction, ), "mae": mean_absolute_error( y_test, prediction,),}
        self.rf_importance = (
            pd.DataFrame({"component": X.columns, "importance": model.feature_importances_,})
            .sort_values("importance", ascending=False,).reset_index(drop=True))
        return self.rf_importance

    # Permutation importance
    def get_permutation_importance(self, n_repeats:int=10, random_state:int=123,) -> pd.DataFrame:
        """Calculate permutation importance for the fitted Random Forest"""
        if self.rf_model is None:
            raise ValueError( "Random Forest has not been fitted." )
        if self.simulation_X is None:
            raise ValueError( "Simulation matrix has not been constructed." )
        X = self.simulation_X
        y = self.simulation_y
        X_train, X_test, y_train, y_test = train_test_split( X, y, test_size=0.2, random_state=random_state, )
        result = permutation_importance( self.rf_model, X_test, y_test, n_repeats=n_repeats, random_state=random_state, n_jobs=-1, )
        self.permutation_importance = (
            pd.DataFrame({"component": X.columns, "importance_mean": result.importances_mean, "importance_std": result.importances_std,})
            .sort_values("importance_mean", ascending=False,).reset_index(drop=True))
        return self.permutation_importance