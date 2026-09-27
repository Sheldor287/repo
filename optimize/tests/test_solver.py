import networkx as nx
import pytest

from toy_models.create import ToyGraph
from models import LP, Solver


class TestSolver:

    def test_initialization(self):
        toy = ToyGraph()
        lp = LP(toy)

        solver = Solver(lp)

        assert solver.lp is lp
        assert solver.g is lp.g
        assert solver.model is lp.model
        assert solver.model_type == lp.model_type

    def test_solver_has_solution_result(self):
        toy = ToyGraph()
        lp = LP(toy)

        solver = Solver(lp)

        assert solver.solver_result is not None

    def test_max_flow_solves(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="max_flow")

        solver = Solver(lp)

        assert solver.solver_result is not None
        assert solver.results is not None

    def test_min_cut_solves(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="min_cut")

        solver = Solver(lp)

        assert solver.solver_result is not None
        assert solver.results is not None

    def test_node_interdiction_solves(self):
        toy = ToyGraph()
        lp = LP(toy, model_type="node_interdiction")

        solver = Solver(lp)

        assert solver.solver_result is not None
        assert solver.results is not None

    def test_results_are_built_after_solving(self):
        toy = ToyGraph()
        lp = LP(toy)

        solver = Solver(lp)

        assert isinstance(solver.results, dict)

    def test_graph_matches_lp(self):
        toy = ToyGraph()
        lp = LP(toy)

        solver = Solver(lp)

        assert solver.g is lp.g
        assert set(solver.g.nodes) == set(lp.g.nodes)
        assert set(solver.g.edges) == set(lp.g.edges)

    def test_model_matches_lp(self):
        toy = ToyGraph()
        lp = LP(toy)

        solver = Solver(lp)

        assert solver.model is lp.model

    def test_solver_from_lp_solve(self):
        toy = ToyGraph()
        lp = LP(toy)

        solver = lp.solve()

        assert isinstance(solver, Solver)
        assert solver.lp is lp
        assert solver.solver_result is not None
        assert solver.results is not None

