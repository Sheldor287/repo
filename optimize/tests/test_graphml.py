import numpy as np
import pandas as pd
import pytest

from toy_models.create import ToyGraph
from models import LP
from analysis import Analysis, GraphML

@pytest.fixture
def toy_graph():
    return ToyGraph()

@pytest.fixture
def max_flow_analysis(toy_graph):
    lp = LP(toy_graph, model_type="max_flow")
    solver = lp.solve()
    return Analysis(solver)

@pytest.fixture
def simulation_df(max_flow_analysis):
    g = max_flow_analysis.g
    nodes = [n for n in g.nodes() if not g.nodes[n].get("artificial", False)]
    edges = [(u, v) for u, v in g.edges() if not g.edges[u, v].get("artificial", False)]
    rows = []
    # Deterministic scenarios with both operational and failed
    # states for every component.
    for i in range(20):
        row = {"sim_number": i, "objective": float(i % 5),}
        for j, node in enumerate(nodes):
            row[f"node_{node}"] = int((i + j) % 2 == 0)
        for j, (u, v) in enumerate(edges):
            row[f"edge_({u},{v})"] = int((i + j) % 2 == 0)
        rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture
def graph_ml(max_flow_analysis, simulation_df):
    return GraphML(analysis=max_flow_analysis, df=simulation_df,)


class TestGraphMLInitialization:

    def test_initialization(self, graph_ml, max_flow_analysis, simulation_df):
        assert graph_ml.analysis is max_flow_analysis
        assert graph_ml.g is max_flow_analysis.g
        assert graph_ml.df is simulation_df

    def test_structural_features_initialized(self, graph_ml):
        assert graph_ml.node_X is not None
        assert isinstance(graph_ml.node_X, pd.DataFrame)

    def test_ml_objects_start_empty(self, graph_ml):
        assert graph_ml.edge_X is None
        assert graph_ml.simulation_X is None
        assert graph_ml.simulation_y is None
        assert graph_ml.node_y is None
        assert graph_ml.edge_y is None
        assert graph_ml.cluster_df is None
        assert graph_ml.rf_model is None
        assert graph_ml.rf_importance is None
        assert graph_ml.permutation_importance is None

    def test_numeric_node_map(self, graph_ml):
        encoder = graph_ml.graph_encoder
        decoder = graph_ml.graph_decoder

        assert len(encoder) == graph_ml.g.number_of_nodes()
        assert len(decoder) == graph_ml.g.number_of_nodes()

        for node, encoded in encoder.items():
            assert decoder[encoded] == node


class TestGraphMLValidation:

    def test_require_data(self, max_flow_analysis):
        ml = GraphML(analysis=max_flow_analysis, df=None,)
        with pytest.raises(ValueError, match="stochastic simulation DataFrame",):
            ml.get_simulation_matrix()

    def test_require_features(self, max_flow_analysis, simulation_df):
        ml = GraphML(analysis=max_flow_analysis, df=simulation_df,)
        ml.node_X = None
        with pytest.raises(ValueError, match="Node feature matrix",):
            ml.cluster_nodes()


class TestSimulationMatrix:

    def test_get_simulation_matrix(self, graph_ml):
        X, y = graph_ml.get_simulation_matrix()
        assert isinstance(X, pd.DataFrame)
        assert isinstance(y, pd.Series)
        assert len(X) == len(graph_ml.df)
        assert len(y) == len(graph_ml.df)
        assert graph_ml.simulation_X is X
        assert graph_ml.simulation_y is y

    def test_simulation_matrix_contains_components(self, graph_ml):
        X, y = graph_ml.get_simulation_matrix()
        assert len(X.columns) > 0
        assert "objective" not in X.columns
        assert y.name == "objective"
        assert all(column.startswith("node_") or column.startswith("edge_") for column in X.columns)

    def test_simulation_matrix_is_binary(self, graph_ml):
        X, _ = graph_ml.get_simulation_matrix()
        assert set(X.to_numpy().ravel()).issubset({0, 1})


class TestTargetMatrices:

    def test_target_matrices(self, graph_ml):
        node_y, edge_y = graph_ml.target_matrices()
        assert isinstance(node_y, pd.DataFrame)
        assert isinstance(edge_y, pd.DataFrame)
        assert graph_ml.node_y is not None
        assert graph_ml.edge_y is not None

    def test_node_targets_have_expected_columns(self, graph_ml):
        node_y, _ = graph_ml.target_matrices()
        expected_columns = {
            "component",
            "value_if_operational",
            "value_if_failed",
            "value_difference",
            "relative_impact",
            "n_operational",
            "n_failed",
            "observed_performance_rate",
        }
        assert expected_columns.issubset(node_y.columns)

    def test_edge_targets_have_expected_columns(self, graph_ml):
        _, edge_y = graph_ml.target_matrices()
        expected_columns = {
            "component",
            "value_if_operational",
            "value_if_failed",
            "value_difference",
            "relative_impact",
            "n_operational",
            "n_failed",
            "observed_performance_rate",
        }
        assert expected_columns.issubset(edge_y.columns)


class TestNodeClustering:

    def test_kmeans_clustering(self, graph_ml):
        n_clusters = 2
        result = graph_ml.cluster_nodes(n_clusters=n_clusters, method="kmeans", random_state=123,)
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == {"node", "cluster"}
        assert len(result) == graph_ml.g.number_of_nodes()
        assert result["node"].is_unique
        assert result["cluster"].nunique() <= n_clusters

    def test_hierarchical_clustering(self, graph_ml):
        result = graph_ml.cluster_nodes(n_clusters=2, method="hierarchical",)
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == {"node", "cluster"}
        assert len(result) == graph_ml.g.number_of_nodes()

    def test_clustering_without_scaling(self, graph_ml):
        result = graph_ml.cluster_nodes(n_clusters=2, method="kmeans", scale=False, random_state=123,)
        assert len(result) == graph_ml.g.number_of_nodes()

    def test_invalid_clustering_method(self, graph_ml):
        with pytest.raises(ValueError, match="method must be 'kmeans' or 'hierarchical'",):
            graph_ml.cluster_nodes(method="invalid")


class TestRandomForest:

    def test_random_forest_regression(self, graph_ml):
        importance = graph_ml.fit_random_forest(classification=False, test_size=0.25, random_state=123, n_estimators=20,)
        assert isinstance(importance, pd.DataFrame)
        assert {"component", "importance"}.issubset(importance.columns)
        assert graph_ml.rf_model is not None
        assert graph_ml.rf_importance is not None
        assert hasattr(graph_ml, "rf_metrics")
        assert "r2" in graph_ml.rf_metrics
        assert "mae" in graph_ml.rf_metrics

    def test_random_forest_importance_matches_features(self, graph_ml):
        importance = graph_ml.fit_random_forest(n_estimators=20, random_state=123,)
        X, _ = graph_ml.get_simulation_matrix()
        assert set(importance["component"]) == set(X.columns)
        assert len(importance) == len(X.columns)

    def test_random_forest_classification(self, graph_ml):
        # Make the target explicitly binary for classification.
        graph_ml.df["objective"] = (graph_ml.df["objective"] > 2).astype(int)
        importance = graph_ml.fit_random_forest(classification=True, test_size=0.25, random_state=123, n_estimators=20,)
        assert isinstance(importance, pd.DataFrame)
        assert graph_ml.rf_model is not None
        assert "accuracy" in graph_ml.rf_metrics

    def test_random_forest_builds_simulation_matrix_automatically(self, graph_ml,):
        assert graph_ml.simulation_X is None
        graph_ml.fit_random_forest(n_estimators=20, random_state=123,)
        assert graph_ml.simulation_X is not None
        assert graph_ml.simulation_y is not None


class TestPermutationImportance:

    def test_requires_random_forest(self, graph_ml):
        graph_ml.get_simulation_matrix()
        with pytest.raises(ValueError, match="Random Forest has not been fitted",):
            graph_ml.get_permutation_importance()

    def test_requires_simulation_matrix(self, graph_ml):
        graph_ml.fit_random_forest(n_estimators=20, random_state=123,)
        graph_ml.simulation_X = None
        with pytest.raises(ValueError, match="Simulation matrix has not been constructed",):
            graph_ml.get_permutation_importance()

    def test_permutation_importance(self, graph_ml):
        graph_ml.fit_random_forest(n_estimators=20, random_state=123,)
        result = graph_ml.get_permutation_importance(n_repeats=2, random_state=123,)
        expected_columns = {"component", "importance_mean", "importance_std",}
        assert expected_columns.issubset(result.columns)
        assert len(result) == len(graph_ml.simulation_X.columns)
        assert graph_ml.permutation_importance is not None

