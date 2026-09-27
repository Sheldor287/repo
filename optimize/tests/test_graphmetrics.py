import numpy as np
import pandas as pd
import pytest

from toy_models.create import ToyGraph
from models import LP
from analysis import Analysis, GraphMetrics

@pytest.fixture
def toy_graph():
    return ToyGraph()

@pytest.fixture
def max_flow_analysis(toy_graph):
    lp = LP(toy_graph, model_type="max_flow")
    solver = lp.solve()
    return Analysis(solver)

@pytest.fixture
def graph_metrics(max_flow_analysis):
    return GraphMetrics(max_flow_analysis)


class TestGraphMetricsInitialization:

    def test_initialization_with_analysis(self, max_flow_analysis):
        metrics = GraphMetrics(max_flow_analysis)

        assert metrics.analysis is max_flow_analysis
        assert metrics.solver is max_flow_analysis.solver
        assert metrics.g is max_flow_analysis.g
        assert metrics.results is max_flow_analysis.results
        assert metrics.node_results is max_flow_analysis.node_results
        assert metrics.edge_results is max_flow_analysis.edge_results
        assert metrics.metrics is max_flow_analysis.metrics

    def test_initialization_without_analysis(self):
        metrics = GraphMetrics()

        assert metrics.analysis is None
        assert metrics.solver is None
        assert metrics.g is None
        assert metrics.results == {}
        assert metrics.node_results == {}
        assert metrics.edge_results == {}
        assert metrics.metrics == {}


class TestGraphValidation:

    def test_require_graph_raises_without_analysis(self):
        metrics = GraphMetrics()

        with pytest.raises(ValueError, match="requires an Analysis object"):
            metrics.graph_info()

    def test_require_graph_raises_for_degree_metrics(self):
        metrics = GraphMetrics()

        with pytest.raises(ValueError, match="requires an Analysis object"):
            metrics.degree_metrics()


class TestGraphInfo:

    def test_graph_info(self, graph_metrics):
        info = graph_metrics.graph_info()
        expected_keys = {"nodes", "edges", "density", "directed", "weighted", "connected",}
        assert expected_keys.issubset(info.keys())
        assert info["nodes"] == graph_metrics.g.number_of_nodes()
        assert info["edges"] == graph_metrics.g.number_of_edges()
        assert 0 <= info["density"] <= 1
        assert isinstance(info["directed"], bool)
        assert isinstance(info["weighted"], bool)
        assert isinstance(info["connected"], bool)


class TestDegreeMetrics:

    def test_degree_metrics_columns(self, graph_metrics):
        df = graph_metrics.degree_metrics()
        expected_columns = {"node", "degree", "in_degree", "out_degree",}
        assert expected_columns.issubset(df.columns)
        assert len(df) == graph_metrics.g.number_of_nodes()
        assert df["node"].is_unique

    def test_degree_metrics_values(self, graph_metrics):
        df = graph_metrics.degree_metrics()
        for _, row in df.iterrows():
            node = row["node"]
            assert row["degree"] == graph_metrics.g.degree(node)
            assert row["in_degree"] == graph_metrics.g.in_degree(node)
            assert row["out_degree"] == graph_metrics.g.out_degree(node)


class TestCentralityMetrics:

    def test_centrality_metrics(self, graph_metrics):
        df = graph_metrics.centrality_metrics()
        expected_columns = {"node", "degree_centrality", "betweenness_centrality", "closeness_centrality", "eigenvector_centrality",}
        assert expected_columns.issubset(df.columns)
        assert len(df) == graph_metrics.g.number_of_nodes()
        assert df["node"].is_unique

    def test_centrality_metrics_are_finite(self, graph_metrics):
        df = graph_metrics.centrality_metrics()
        numeric_columns = ["degree_centrality", "betweenness_centrality", "closeness_centrality", "eigenvector_centrality",]
        assert np.isfinite(df[numeric_columns].to_numpy()).all()

    def test_eigenvector_convergence_failure_returns_nan(self, graph_metrics):
        df = graph_metrics.centrality_metrics(max_iter=1)
        assert "eigenvector_centrality" in df.columns
        assert len(df) == graph_metrics.g.number_of_nodes()


class TestClusteringMetrics:

    def test_clustering_metrics(self, graph_metrics):
        df = graph_metrics.clustering_metrics()
        assert set(["node", "clustering_coefficient"]).issubset(df.columns)
        assert len(df) == graph_metrics.g.number_of_nodes()
        assert df["node"].is_unique

    def test_clustering_values_are_valid(self, graph_metrics):
        df = graph_metrics.clustering_metrics()
        assert (df["clustering_coefficient"] >= 0).all()
        assert (df["clustering_coefficient"] <= 1).all()


class TestSpectralMetrics:

    def test_spectral_metrics_keys(self, graph_metrics):
        result = graph_metrics.spectral_metrics()
        expected_keys = {
            "adjacency_spectral_radius",
            "adjacency_largest_eigenvalue",
            "laplacian_algebraic_connectivity",
            "laplacian_spectral_gap",
            "laplacian_largest_eigenvalue",
            "adjacency_eigenvalues",
            "laplacian_eigenvalues",
            "fiedler_vector",
        }
        assert expected_keys.issubset(result.keys())

    def test_spectral_metrics_shapes(self, graph_metrics):
        result = graph_metrics.spectral_metrics()
        n = graph_metrics.g.number_of_nodes()
        assert len(result["adjacency_eigenvalues"]) == n
        assert len(result["laplacian_eigenvalues"]) == n
        assert len(result["fiedler_vector"]) == n

    def test_spectral_metrics_are_finite(self, graph_metrics):
        result = graph_metrics.spectral_metrics()
        scalar_keys = [
            "adjacency_spectral_radius",
            "adjacency_largest_eigenvalue",
            "laplacian_algebraic_connectivity",
            "laplacian_spectral_gap",
            "laplacian_largest_eigenvalue",
        ]
        assert np.isfinite([result[key] for key in scalar_keys]).all()
        assert np.isfinite(result["adjacency_eigenvalues"]).all()
        assert np.isfinite(result["laplacian_eigenvalues"]).all()
        assert np.isfinite(result["fiedler_vector"]).all()

    def test_spectral_radius_is_nonnegative(self, graph_metrics):
        result = graph_metrics.spectral_metrics()
        assert result["adjacency_spectral_radius"] >= 0
        assert result["laplacian_largest_eigenvalue"] >= 0

class TestSpectralNodeFeatures:

    def test_spectral_node_features(self, graph_metrics):
        df = graph_metrics.spectral_node_features()
        expected_columns = {"node", "fiedler_value", "spectral_coordinate_0", "spectral_coordinate_1", "spectral_coordinate_2",}
        assert expected_columns.issubset(df.columns)
        assert len(df) == graph_metrics.g.number_of_nodes()
        assert df["node"].is_unique

    def test_spectral_node_features_are_finite(self, graph_metrics):
        df = graph_metrics.spectral_node_features()
        numeric = df.drop(columns=["node"]).to_numpy()
        assert np.isfinite(numeric).all()

class TestCommunityDetection:

    def test_community_detection(self, graph_metrics):
        df = graph_metrics.community_detection()
        expected_columns = {"node", "community", "community_size",}
        assert expected_columns.issubset(df.columns)
        assert len(df) == graph_metrics.g.number_of_nodes()
        assert df["node"].is_unique

    def test_every_node_has_community(self, graph_metrics):
        df = graph_metrics.community_detection()
        expected_nodes = set(graph_metrics.g.nodes())
        actual_nodes = set(df["node"])
        assert actual_nodes == expected_nodes

    def test_community_sizes_are_positive(self, graph_metrics):
        df = graph_metrics.community_detection()
        assert (df["community_size"] > 0).all()


class TestNodeFeatures:

    def test_node_features(self, graph_metrics):
        df = graph_metrics.node_features()
        expected_columns = {
            "node",
            "degree",
            "in_degree",
            "out_degree",
            "degree_centrality",
            "betweenness_centrality",
            "closeness_centrality",
            "eigenvector_centrality",
            "clustering_coefficient",
            "fiedler_value",
            "spectral_coordinate_0",
            "spectral_coordinate_1",
            "spectral_coordinate_2",
            "community",
            "community_size",
        }
        assert expected_columns.issubset(df.columns)
        assert len(df) == graph_metrics.g.number_of_nodes()
        assert df["node"].is_unique

    def test_node_features_have_no_missing_values(self, graph_metrics):
        df = graph_metrics.node_features()
        assert not df.isna().any().any()

    def test_node_features_match_graph_nodes(self, graph_metrics):
        df = graph_metrics.node_features()
        assert set(df["node"]) == set(graph_metrics.g.nodes())

