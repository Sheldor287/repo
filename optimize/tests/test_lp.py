import pytest
import networkx as nx
import pyomo.environ as pyo
from equations import Rules
from toy_models.create import ToyGraph
from models import LP


class TestLP:

    def test_default_initialization(self):
        toy = ToyGraph()
        lp = LP(toy)

        assert isinstance(lp.g, nx.DiGraph)
        assert lp.model_type == "max_flow"
        assert lp.s == "s"
        assert lp.t == "t"
        assert lp.solver_str == "appsi_highs"
        assert isinstance(lp.r, Rules)
        assert lp.model is not None

    def test_graph_is_copied(self):
        toy = ToyGraph()
        lp = LP(toy)

        assert lp.g is not toy.G

        original_nodes = set(toy.G.nodes)
        lp.g.remove_node(next(iter(lp.g.nodes)))

        assert set(toy.G.nodes) == original_nodes

    def test_alternate_model_names(self):
        toy = ToyGraph()

        aliases = {
            "max_flow": "max_flow",
            "mf": "max_flow",
            "standard_max_flow": "max_flow",
            "standard_mf": "max_flow",
            "dual_maxflow": "min_cut",
            "min_cut": "min_cut",
            "min_cut_flow": "min_cut",
            "zerosum_mf_static_nodes": "node_interdiction",
            "interdiction": "node_interdiction",
            "node_interdiction": "node_interdiction",
        }

        for alias, expected in aliases.items():
            lp = LP(toy, model_type=alias)
            assert lp.model_type == expected

    def test_invalid_model_type(self):
        toy = ToyGraph()

        with pytest.raises(ValueError, match="Unknown model type"):
            LP(toy, model_type="not_a_model")

    def test_graph_attributes_are_standardized(self):
        toy = ToyGraph()
        lp = LP(toy)

        for _, _, data in lp.g.edges(data=True):
            assert "capacity" in data
            assert "cost" in data

        for _, data in lp.g.nodes(data=True):
            assert "demand" in data

    def test_super_source_and_sink_exist(self):
        toy = ToyGraph()
        lp = LP(toy)

        assert lp.s in lp.g.nodes
        assert lp.t in lp.g.nodes

        assert lp.g.nodes[lp.s]["artificial"] is True
        assert lp.g.nodes[lp.t]["artificial"] is True

    def test_base_model_sets(self):
        toy = ToyGraph()
        lp = LP(toy)

        assert set(lp.model.nodes) == set(lp.g.nodes)
        assert set(lp.model.edges) == set(lp.g.edges)

    def test_base_model_parameters(self):
        toy = ToyGraph()
        lp = LP(toy)

        model = lp.model

        for node in model.nodes:
            assert pyo.value(model.node_state[node]) == 1
            assert pyo.value(model.artificial_node[node]) in (0, 1)

        for edge in model.edges:
            u, v = edge

            assert pyo.value(model.capacity[u, v]) == lp.g.edges[u, v]["capacity"]
            assert pyo.value(model.cost[u, v]) == lp.g.edges[u, v]["cost"]
            assert pyo.value(model.edge_state[u, v]) in (0, 1)
            assert pyo.value(model.artificial_edge[u, v]) in (0, 1)

    def test_max_flow_model_structure(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="max_flow")

        model = lp.model

        assert hasattr(model, "x")
        assert hasattr(model, "F")
        assert hasattr(model, "cap")
        assert hasattr(model, "flow")
        assert hasattr(model, "source")
        assert hasattr(model, "sink")
        assert hasattr(model, "dual")

        assert model.x.is_indexed()
        assert model.F.is_variable_type()

    def test_min_cut_model_structure(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="min_cut")

        model = lp.model

        assert hasattr(model, "theta")
        assert hasattr(model, "alpha")
        assert hasattr(model, "cutset")
        assert hasattr(model, "stflow")

        assert model.theta.is_indexed()
        assert model.alpha.is_indexed()

    def test_node_interdiction_model_structure(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="node_interdiction")

        model = lp.model

        assert hasattr(model, "theta")
        assert hasattr(model, "alpha")
        assert hasattr(model, "omega")
        assert hasattr(model, "z")

        assert hasattr(model, "M")
        assert hasattr(model, "interdiction_cost")
        assert hasattr(model, "budget")

        assert hasattr(model, "budget_limit")
        assert hasattr(model, "artificial_protection")
        assert hasattr(model, "z1")
        assert hasattr(model, "z2")
        assert hasattr(model, "z3")
        assert hasattr(model, "z4")

        assert model.M.value == 1
        assert model.budget.value == 9

    def test_solve_returns_solver(self):
        toy = ToyGraph()
        lp = LP(toy)

        solver = lp.solve()

        assert solver is not None

    def test_fix_interdiction(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="node_interdiction")

        interdicted = [0, 1]
        lp.fix_interdiction(interdicted)

        for node in lp.model.nodes:
            expected = 1 if node in interdicted else 0
            assert lp.model.omega[node].fixed
            assert pyo.value(lp.model.omega[node]) == expected

    def test_fix_interdiction_rejects_non_interdiction_model(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="max_flow")
        with pytest.raises(ValueError, match="Interdiction decisions only exist",):
            lp.fix_interdiction([0])

