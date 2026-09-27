from toy_models.create import ToyGraph
def test_toy_graph_creation():
    toy = ToyGraph()
    assert toy.G is not None
    assert toy.G.number_of_nodes() > 0
    assert toy.G.number_of_edges() > 0

