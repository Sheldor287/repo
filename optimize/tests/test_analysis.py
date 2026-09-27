import numpy as np
import pandas as pd
import pytest

from toy_models.create import ToyGraph
from models import LP
from analysis import Analysis

# Fixtures
@pytest.fixture
def toy_graph():
    return ToyGraph()

@pytest.fixture
def max_flow_analysis(toy_graph):
    lp = LP(toy_graph, model_type="max_flow")
    solver = lp.solve()
    return Analysis(solver)

@pytest.fixture
def simulation_df():
    return pd.DataFrame(
        {
            "objective": [10, 8, 6, 4, 0],
            "node_failed": [0, 1, 2, 2, 3],
            "edge_failed": [0, 0, 1, 2, 3],
            "node_0": [1, 1, 0, 0, 0],
            "node_1": [1, 0, 1, 0, 0],
            "edge_(0,1)": [1, 1, 1, 0, 0],
            "edge_(1,2)": [1, 1, 0, 0, 0],
        }
    )

# Construction
class TestAnalysisInitialization:

    def test_initialization(self, max_flow_analysis):
        analysis = max_flow_analysis

        assert analysis.solver is not None
        assert analysis.g is analysis.solver.g
        assert analysis.model is analysis.solver.model
        assert analysis.model_type == analysis.solver.model_type

        assert isinstance(analysis.results, dict)
        assert isinstance(analysis.node_results, dict)
        assert isinstance(analysis.edge_results, dict)
        assert isinstance(analysis.metrics, dict)
        assert isinstance(analysis.problem, dict)
        assert isinstance(analysis.solver_results, dict)

    def test_simulation_attributes_start_uninitialized(self, max_flow_analysis):
        analysis = max_flow_analysis

        assert analysis.nodes is None
        assert analysis.edges is None
        assert analysis.node_p is None
        assert analysis.edge_p is None



# Summary / result access
class TestAnalysisResults:

    def test_summary(self, max_flow_analysis):
        analysis = max_flow_analysis

        summary = analysis.summary()

        expected = {
            "model_type",
            "objective_value",
            "status",
            "termination_condition",
            "cut_capacity",
            "capacity_removed",
            "interdiction_cost",
            "budget",
        }

        assert set(summary) == expected
        assert summary["model_type"] == "max_flow"

    def test_get_objective_value(self, max_flow_analysis):
        analysis = max_flow_analysis
        assert (analysis.get_objective_value() == analysis.problem.get("objective_value"))

    def test_get_node_results(self, max_flow_analysis):
        analysis = max_flow_analysis
        assert analysis.get_node_results() is analysis.node_results

    def test_get_edge_results(self, max_flow_analysis):
        analysis = max_flow_analysis
        assert analysis.get_edge_results() is analysis.edge_results

    def test_get_metrics(self, max_flow_analysis):
        analysis = max_flow_analysis
        assert analysis.get_metrics() is analysis.metrics


# Cut analysis
class TestCutAnalysis:

    def test_get_cut_edges(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.edge_results = {(0, 1): {"in_cut": True}, (1, 2): {"in_cut": False}, (2, 3): {"in_cut": True},}
        assert set(analysis.get_cut_edges()) == {(0, 1), (2, 3),}

    def test_get_interdicted_cut_edges(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.edge_results = {
            (0, 1): {"in_interdicted_cut": True},
            (1, 2): {"in_interdicted_cut": False},
            (2, 3): {"in_interdicted_cut": True},
        }
        assert set(analysis.get_interdicted_cut_edges()) == {(0, 1), (2, 3),}

    def test_get_cut_capacity(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.metrics = {"cut_capacity": 12}
        assert analysis.get_cut_capacity() == 12

    def test_get_capacity_removed(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.metrics = {"capacity_removed": 7}
        assert analysis.get_capacity_removed() == 7

    def test_default_capacity_removed(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.metrics = {}
        assert analysis.get_capacity_removed() == 0



# Interdiction analysis
class TestInterdictionAnalysis:

    def test_get_interdicted_nodes(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.node_results = {
            0: {"interdicted": True},
            1: {"interdicted": False},
            2: {"interdicted": True},
        }
        assert set(analysis.get_interdicted_nodes()) == {0, 2}

    def test_get_interdiction_cost(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.metrics = {"interdiction_cost": 15}
        assert analysis.get_interdiction_cost() == 15

    def test_get_interdiction_cost_default(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.metrics = {}
        assert analysis.get_interdiction_cost() == 0

    def test_interdiction_efficiency(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.metrics = {"interdiction_cost": 5, "capacity_removed": 20,}
        assert analysis.get_interdiction_efficiency() == 4

    def test_interdiction_efficiency_zero_cost(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis.metrics = {"interdiction_cost": 0, "capacity_removed": 20,}
        assert analysis.get_interdiction_efficiency() is None



# Simulation preprocessing
class TestSimulationHelpers:

    def test_preprocess_excludes_artificial_components(self, max_flow_analysis,):
        analysis = max_flow_analysis
        analysis._preprocess_network_simulation()
        assert analysis.nodes is not None
        assert analysis.edges is not None
        assert analysis.node_p is not None
        assert analysis.edge_p is not None
        for node in analysis.nodes:
            assert not analysis.g.nodes[node].get("artificial", False)

        for u, v in analysis.edges:
            assert not analysis.g.edges[u, v].get("artificial", False)

    def test_probability_arrays_match_components(self, max_flow_analysis,):
        analysis = max_flow_analysis
        analysis._preprocess_network_simulation()
        assert len(analysis.node_p) == len(analysis.nodes)
        assert len(analysis.edge_p) == len(analysis.edges)
        assert np.all((analysis.node_p >= 0) & (analysis.node_p <= 1))
        assert np.all((analysis.edge_p >= 0) & (analysis.edge_p <= 1))

    def test_sample_states_are_binary(self, max_flow_analysis):
        analysis = max_flow_analysis
        analysis._preprocess_network_simulation()
        rng = np.random.default_rng(123)
        node_state, edge_state = analysis._sample_states(rng)
        assert len(node_state) == len(analysis.nodes)
        assert len(edge_state) == len(analysis.edges)
        assert set(node_state).issubset({0, 1})
        assert set(edge_state).issubset({0, 1})

# Monte Carlo simulation
class TestStochasticAnalysis:

    def test_stochastic_analysis_shape(self, max_flow_analysis):
        analysis = max_flow_analysis
        df = analysis.stochastic_analysis(n_sim=5, seed=123,)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5

    def test_stochastic_analysis_columns(self, max_flow_analysis):
        analysis = max_flow_analysis
        df = analysis.stochastic_analysis(n_sim=3, seed=123,)
        expected = {
            "sim_number",
            "objective",
            "node_operational",
            "node_failed",
            "edge_operational",
            "edge_failed",
            "node_opr_ratio",
            "edge_opr_ratio",
            "termination_condition",
            "flow",
            "flow_failure_indicator",
        }
        assert expected.issubset(df.columns)

    def test_stochastic_analysis_reproducible(self, max_flow_analysis):
        analysis = max_flow_analysis
        df1 = analysis.stochastic_analysis(n_sim=5, seed=123,)
        df2 = analysis.stochastic_analysis(n_sim=5, seed=123,)
        pd.testing.assert_frame_equal(df1, df2)

    def test_simulation_numbers(self, max_flow_analysis):
        analysis = max_flow_analysis
        df = analysis.stochastic_analysis(n_sim=5, seed=123,)
        assert df["sim_number"].tolist() == [0, 1, 2, 3, 4]

    def test_component_state_columns_are_binary(self, max_flow_analysis):
        analysis = max_flow_analysis
        df = analysis.stochastic_analysis(n_sim=5, seed=123,)
        node_cols, edge_cols = analysis._get_component_columns(df)
        for column in node_cols + edge_cols:
            assert set(df[column].unique()).issubset({0, 1})

# Reliability
class TestReliability:

    def test_reliability(self, simulation_df):
        result = Analysis.reliability(simulation_df, threshold=6,)
        assert result == pytest.approx(3 / 5)

    def test_failure_probability(self, simulation_df):
        result = Analysis.failure_probability(simulation_df, threshold=6,)
        assert result == pytest.approx(2 / 5)

    def test_reliability_curve(self, simulation_df):
        curve = Analysis.reliability_curve(simulation_df)
        assert list(curve.columns) == ["requirement", "reliability",]
        assert curve["requirement"].tolist() == [0, 4, 6, 8, 10,]
        assert curve.loc[curve["requirement"] == 6, "reliability",].iloc[0] == pytest.approx(3 / 5)

    def test_performance_distribution(self, simulation_df):
        result = Analysis.performance_distribution(simulation_df, threshold=6,)
        assert result["mean"] == pytest.approx(5.6)
        assert result["median"] == 6
        assert result["min"] == 0
        assert result["max"] == 10
        assert result["zero_probability"] == pytest.approx(1 / 5)
        assert result["reliability"] == pytest.approx(3 / 5)
        assert result["probability_of_failure"] == pytest.approx(2 / 5)

    def test_performance_distribution_empty(self):
        df = pd.DataFrame({"objective": []})
        result = Analysis.performance_distribution(df)
        assert result == {}

    def test_expected_shortfall(self, simulation_df):
        result = Analysis.expected_shortfall(simulation_df, threshold=6,)
        # Values below 6 are 4 and 0.
        assert result == pytest.approx(2)

    def test_expected_shortfall_without_failures(self, simulation_df):
        result = Analysis.expected_shortfall(simulation_df, threshold=0,)
        assert np.isnan(result)

# Performance summary / resilience
class TestPerformanceSummary:

    def test_performance_summary_without_threshold(self, simulation_df,):
        result = Analysis.performance_summary(Analysis.__new__(Analysis), simulation_df,)
        assert "mean" in result
        assert "median" in result
        assert "std" in result
        assert "variance" in result

    def test_performance_summary_with_threshold(self, max_flow_analysis, simulation_df,):
        result = max_flow_analysis.performance_summary(simulation_df, threshold=6,)
        assert result["reliability"] == pytest.approx(3 / 5)
        assert result["failure_probability"] == pytest.approx(2 / 5)
        assert result["expected_shortfall"] == pytest.approx(2)


class TestResilience:

    def test_resilience_curve(self, simulation_df):
        curve = Analysis.resilience_curve(simulation_df, y_column="objective", failure_column="node_failed", baseline=10,)
        assert list(curve.columns) == ["node_failed", "mean", "median", "std", "count", "relative_performance",]
        row = curve[curve["node_failed"] == 2].iloc[0]
        assert row["mean"] == pytest.approx(5)
        assert row["count"] == 2
        assert row["relative_performance"] == pytest.approx(0.5)

    def test_resilience_curve_automatic_baseline(self, simulation_df,):
        curve = Analysis.resilience_curve(simulation_df, y_column="objective", failure_column="node_failed",)
        assert curve["relative_performance"].max() == pytest.approx(1)

    def test_resilience_curve_empty(self):
        df = pd.DataFrame(columns=["objective", "node_failed"])
        curve = Analysis.resilience_curve(df, y_column="objective", failure_column="node_failed",)
        assert curve.empty

# Component influence
class TestComponentInfluence:

    def test_get_component_columns(self, simulation_df):
        node_cols, edge_cols = Analysis._get_component_columns(simulation_df)
        assert node_cols == ["node_0", "node_1",]
        assert edge_cols == ["edge_(0,1)", "edge_(1,2)",]

    def test_influence_logic(self, simulation_df):
        node_cols, _ = Analysis._get_component_columns(simulation_df)
        result = Analysis._get_influence_logic(simulation_df, node_cols,)
        assert isinstance(result, pd.DataFrame)
        expected = {
            "component",
            "value_if_operational",
            "value_if_failed",
            "value_difference",
            "relative_impact",
            "n_operational",
            "n_failed",
            "observed_performance_rate",
        }
        assert expected.issubset(result.columns)

    def test_get_component_influence(self, max_flow_analysis, simulation_df,):
        node_results, edge_results = (max_flow_analysis.get_component_influence(simulation_df))
        assert isinstance(node_results, pd.DataFrame)
        assert isinstance(edge_results, pd.DataFrame)
        assert len(node_results) == 2
        assert len(edge_results) == 2
        assert set(node_results["component"]) == {"node_0", "node_1",}
        assert set(edge_results["component"]) == {"edge_(0,1)", "edge_(1,2)",}



# Component reliability
class TestComponentReliability:

    def test_component_reliability(self, max_flow_analysis, simulation_df,):
        result = max_flow_analysis.get_component_reliability(simulation_df, threshold=6,)
        assert isinstance(result, pd.DataFrame)
        expected = {
            "component",
            "component_type",
            "reliability_if_operational",
            "reliability_if_failed",
            "reliability_impact",
            "n_operational",
            "n_failed",
            "observed_failure_rate",
        }
        assert expected.issubset(result.columns)
        assert len(result) == 4
        assert set(result["component_type"]) == {"node", "edge",}

# Workflow metadata
class TestAnalysisWorkflow:

    def test_analysis_step_metadata(self):
        assert hasattr(Analysis.summary, "_analysis_category")
        assert hasattr(Analysis.summary, "_analysis_description")
        assert Analysis.summary._analysis_category == "Solution"
        assert (Analysis.summary._analysis_description == "General solution information")

    def test_workflow_runs(self, capsys):
        Analysis.show_workflow()
        captured = capsys.readouterr()
        assert "Analysis — Analysis Workflow" in captured.out
        assert "Solution" in captured.out
        assert "Reliability" in captured.out
        assert "Monte Carlo" in captured.out

