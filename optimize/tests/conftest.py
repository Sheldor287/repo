import pytest
from toy_models.create import ToyGraph
from models import LP, Solver
from analysis import Analysis
from analysis import GraphMetrics

@pytest.fixture
def toy_graph():
    return ToyGraph(layer_list=[1, 2, 2, 1], seed=123)

@pytest.fixture
def lp(toy_graph):
    return LP(toy_graph.G, model_type="max_flow")

@pytest.fixture
def solver(lp):
    return Solver(lp)

@pytest.fixture
def analysis(solver):
    return Analysis(solver)

@pytest.fixture
def graph_metrics(analysis):
    return GraphMetrics(analysis)


