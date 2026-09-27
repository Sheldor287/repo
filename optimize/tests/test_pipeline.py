import numpy as np
import pandas as pd
import pytest

from toy_models.create import ToyGraph
from models import LP
from analysis import Analysis, GraphMetrics, GraphML
from display import GraphDrawer

@pytest.fixture
def toy_graph():
    return ToyGraph()

@pytest.fixture
def lp(toy_graph):
    return LP(toy_graph, model_type="max_flow",)

@pytest.fixture
def solver(lp):
    return lp.solve()

@pytest.fixture
def analysis(solver):
    return Analysis(solver)

@pytest.fixture
def graph_metrics(analysis):
    return GraphMetrics(analysis)

@pytest.fixture
def simulation_df(analysis):
    """
    Small deterministic simulation dataset for testing the ML layer
    without repeatedly running stochastic optimization.
    """
    nodes = [n for n in analysis.g.nodes() if not analysis.g.nodes[n].get("artificial", False)]
    edges = [(u, v) for u, v in analysis.g.edges() if not analysis.g.edges[u, v].get("artificial", False)]
    rows = []
    for i in range(20):
        row = {"sim_number": i, "objective": float(i % 5),}
        for j, node in enumerate(nodes):
            row[f"node_{node}"] = int((i + j) % 2 == 0)
        for j, (u, v) in enumerate(edges):
            row[f"edge_({u},{v})"] = int((i + j) % 2 == 0)
        rows.append(row)
    return pd.DataFrame(rows)

@pytest.fixture
def graph_ml(analysis, simulation_df):
    return GraphML(analysis=analysis, df=simulation_df,)


class TestPipelineConstruction:

    def test_toy_graph_to_lp(self, toy_graph, lp):
        assert lp.g is not toy_graph.G
        original_nodes = set(toy_graph.G.nodes())
        original_edges = set(toy_graph.G.edges())
        assert original_nodes.issubset(set(lp.g.nodes()))
        assert original_edges.issubset(set(lp.g.edges()))
        assert lp.model_type == "max_flow"
        assert lp.model is not None

    def test_lp_to_solver(self, lp, solver):
        assert solver.lp is lp
        assert solver.g is lp.g
        assert solver.model is lp.model
        assert solver.model_type == lp.model_type

    def test_solver_to_analysis(self, solver, analysis):
        assert analysis.solver is solver
        assert analysis.g is solver.g
        assert analysis.model is solver.model
        assert analysis.model_type == solver.model_type
        assert analysis.results is solver.results

    def test_analysis_to_graph_metrics(self, analysis, graph_metrics):
        assert graph_metrics.analysis is analysis
        assert graph_metrics.solver is analysis.solver
        assert graph_metrics.g is analysis.g
        assert graph_metrics.results is analysis.results

    def test_analysis_to_graph_ml(self, analysis, graph_ml):
        assert graph_ml.analysis is analysis
        assert graph_ml.g is analysis.g
        assert graph_ml.df is not None
        assert graph_ml.node_X is not None


class TestPipelineDataFlow:

    def test_solver_results_reach_analysis(self, solver, analysis):
        assert analysis.results == solver.results
        assert analysis.node_results == solver.results.get("node_results", {},)
        assert analysis.edge_results == solver.results.get("edge_results", {},)
        assert analysis.metrics == solver.results.get("metrics", {},)

    def test_analysis_data_reaches_graph_metrics(self, analysis, graph_metrics,):
        info = graph_metrics.graph_info()
        assert info["nodes"] == analysis.g.number_of_nodes()
        assert info["edges"] == analysis.g.number_of_edges()

    def test_graph_metrics_produces_node_features(self, graph_metrics,):
        df = graph_metrics.node_features()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == graph_metrics.g.number_of_nodes()
        assert "node" in df.columns
        assert df["node"].is_unique

    def test_graph_ml_consumes_node_features(self, graph_ml,):
        assert isinstance(graph_ml.node_X, pd.DataFrame)
        assert len(graph_ml.node_X) == graph_ml.g.number_of_nodes()
        assert "node" in graph_ml.node_X.columns


class TestPipelineAnalysis:

    def test_analysis_summary(self, analysis):
        summary = analysis.summary()

        assert isinstance(summary, dict)
        assert summary["model_type"] == "max_flow"
        assert "objective_value" in summary
        assert "status" in summary
        assert "termination_condition" in summary

    def test_analysis_accessors(self, analysis):
        assert analysis.get_node_results() is analysis.node_results
        assert analysis.get_edge_results() is analysis.edge_results
        assert analysis.get_metrics() is analysis.metrics

    def test_cut_analysis(self, analysis):
        cut_edges = analysis.get_cut_edges()

        assert isinstance(cut_edges, list)

    def test_objective_is_numeric(self, analysis):
        objective = analysis.get_objective_value()

        assert objective is not None
        assert np.isfinite(objective)


class TestPipelineML:

    def test_simulation_matrix(self, graph_ml,):
        X, y = graph_ml.get_simulation_matrix()
        assert isinstance(X, pd.DataFrame)
        assert isinstance(y, pd.Series)
        assert len(X) == len(graph_ml.df)
        assert len(y) == len(graph_ml.df)
        assert len(X.columns) > 0

    def test_target_matrices(self, graph_ml,):
        node_y, edge_y = graph_ml.target_matrices()
        assert isinstance(node_y, pd.DataFrame)
        assert isinstance(edge_y, pd.DataFrame)
        assert graph_ml.node_y is not None
        assert graph_ml.edge_y is not None

    def test_node_clustering(self, graph_ml,):
        result = graph_ml.cluster_nodes(n_clusters=2, method="kmeans", random_state=123,)
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == {"node", "cluster"}
        assert len(result) == graph_ml.g.number_of_nodes()

    def test_random_forest(self, graph_ml,):
        importance = graph_ml.fit_random_forest(n_estimators=20, test_size=0.25, random_state=123,)
        assert isinstance(importance, pd.DataFrame)
        assert "component" in importance.columns
        assert "importance" in importance.columns
        assert graph_ml.rf_model is not None

    def test_permutation_importance(self, graph_ml,):
        graph_ml.fit_random_forest(n_estimators=20, test_size=0.25, random_state=123,)
        importance = graph_ml.get_permutation_importance(n_repeats=2, random_state=123,)
        assert isinstance(importance, pd.DataFrame)
        expected_columns = {"component", "importance_mean", "importance_std",}
        assert expected_columns.issubset(importance.columns)


class TestPipelineVisualization:

    def test_graph_drawer_consumes_solver(self, solver,):
        drawer = GraphDrawer(solver)
        assert drawer.solver is solver
        assert drawer.g is solver.g
        assert drawer.model is solver.model
        assert drawer.model_type == solver.model_type

    def test_graph_drawer_default_mode(self, solver,):
        drawer = GraphDrawer(solver)
        expected_mode = GraphDrawer.DEFAULT_DRAWING_MODE[solver.model_type]
        assert expected_mode in GraphDrawer.DRAWING_CONFIG
        assert solver.model_type in GraphDrawer.DRAWING_CONFIG[expected_mode]["models"]


class TestFullPipeline:

    def test_complete_pipeline(self, toy_graph, lp, solver, analysis, graph_metrics, graph_ml,):

        # ToyGraph
        assert toy_graph.G.number_of_nodes() > 0
        # LP
        assert lp.model is not None
        # Solver
        assert solver.results is not None
        # Analysis
        summary = analysis.summary()
        assert summary["model_type"] == "max_flow"

        # GraphMetrics
        info = graph_metrics.graph_info()
        node_features = graph_metrics.node_features()
        assert info["nodes"] == len(node_features)
        assert node_features["node"].is_unique
        # GraphML
        X, y = graph_ml.get_simulation_matrix()
        assert len(X) == len(y)
        assert len(X) == len(graph_ml.df)
        assert graph_ml.node_X is not None

    def test_pipeline_preserves_graph_structure(self, toy_graph, lp, solver, analysis, graph_metrics, graph_ml):
        expected_nodes = set(toy_graph.G.nodes())
        expected_edges = set(toy_graph.G.edges())
        for component in [lp, solver, analysis, graph_metrics, graph_ml]:
            assert expected_nodes.issubset(set(component.g.nodes()))
            assert expected_edges.issubset(set(component.g.edges()))

