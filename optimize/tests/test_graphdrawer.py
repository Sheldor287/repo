import matplotlib.pyplot as plt
import pytest

from toy_models.create import ToyGraph
from models import LP
from display import GraphDrawer

@pytest.fixture
def toy_graph():
    return ToyGraph()

@pytest.fixture
def max_flow_solver(toy_graph):
    lp = LP(toy_graph, model_type="max_flow")
    return lp.solve()

@pytest.fixture
def min_cut_solver(toy_graph):
    lp = LP(toy_graph, model_type="min_cut")
    return lp.solve()

@pytest.fixture
def interdiction_solver(toy_graph):
    lp = LP(toy_graph, model_type="node_interdiction")
    return lp.solve()

@pytest.fixture
def max_flow_drawer(max_flow_solver):
    return GraphDrawer(max_flow_solver)

@pytest.fixture
def min_cut_drawer(min_cut_solver):
    return GraphDrawer(min_cut_solver)

@pytest.fixture
def interdiction_drawer(interdiction_solver):
    return GraphDrawer(interdiction_solver)

@pytest.fixture
def positions(max_flow_drawer):
    return {node: (float(i), 0.0) for i, node in enumerate(max_flow_drawer.g.nodes())}


class TestGraphDrawerInitialization:

    def test_initialization(self, max_flow_drawer, max_flow_solver):
        assert max_flow_drawer.solver is max_flow_solver
        assert max_flow_drawer.lp is max_flow_solver.lp
        assert max_flow_drawer.g is max_flow_solver.g
        assert max_flow_drawer.model is max_flow_solver.model
        assert max_flow_drawer.model_type == max_flow_solver.model_type

    def test_default_properties(self, max_flow_drawer):
        assert max_flow_drawer.node_size == 500
        assert max_flow_drawer.cut_color == "#ff0000"
        assert max_flow_drawer.cmap is not None

    def test_custom_properties(self, max_flow_solver):
        drawer = GraphDrawer(max_flow_solver, node_size=750, cut_color="#00ff00",)
        assert drawer.node_size == 750
        assert drawer.cut_color == "#00ff00"


class TestDrawingConfiguration:

    def test_all_drawing_modes_have_configuration(self):
        expected_modes = {"flow", "residual", "demand", "cost", "cut", "interdiction",}
        assert set(GraphDrawer.DRAWING_CONFIG) == expected_modes

    def test_default_modes(self):
        assert GraphDrawer.DEFAULT_DRAWING_MODE == {"max_flow": "flow", "min_cut": "cut", "node_interdiction": "interdiction",}

    def test_every_mode_has_builder(self):
        for mode, config in GraphDrawer.DRAWING_CONFIG.items():
            assert "builder" in config
            assert "models" in config
            assert isinstance(config["models"], set)

    def test_every_mode_has_colormap(self):
        for mode in GraphDrawer.DRAWING_CONFIG:
            assert mode in GraphDrawer.CMAPS
            assert GraphDrawer.CMAPS[mode] is not None


class TestModeValidation:

    def test_valid_max_flow_modes(self, max_flow_drawer):
        for mode in ["flow", "residual", "demand", "cost"]:
            max_flow_drawer._validate_mode(mode)

    def test_valid_min_cut_mode(self, min_cut_drawer):
        min_cut_drawer._validate_mode("cut")

    def test_valid_interdiction_modes(self, interdiction_drawer):
        interdiction_drawer._validate_mode("cut")
        interdiction_drawer._validate_mode("interdiction")

    def test_invalid_mode(self, max_flow_drawer):
        with pytest.raises(ValueError, match="Unknown drawing mode",):
            max_flow_drawer._validate_mode("invalid")

    def test_incompatible_mode(self, max_flow_drawer):
        with pytest.raises(ValueError, match="not available for model type",):
            max_flow_drawer._validate_mode("cut")

    def test_interdiction_not_available_for_max_flow(self, max_flow_drawer,):
        with pytest.raises(ValueError, match="not available for model type",):
            max_flow_drawer._validate_mode("interdiction")


class TestFlowNodeColors:

    def test_flow_node_colors(self, max_flow_drawer):
        colors = max_flow_drawer._get_flow_node_colors()
        assert len(colors) == max_flow_drawer.g.number_of_nodes()

    def test_flow_node_colors_are_valid(self, max_flow_drawer):
        colors = max_flow_drawer._get_flow_node_colors()

        for color in colors:
            # Matplotlib should be able to interpret every returned color.
            from matplotlib.colors import to_rgba
            rgba = to_rgba(color)
            assert len(rgba) == 4
            assert all(0 <= value <= 1 for value in rgba)


class TestCutNodeColors:

    def test_cut_node_colors(self, min_cut_drawer):
        colors = min_cut_drawer._get_cut_node_colors()
        assert len(colors) == min_cut_drawer.g.number_of_nodes()

    def test_cut_node_colors_are_valid(self, min_cut_drawer):
        colors = min_cut_drawer._get_cut_node_colors()
        from matplotlib.colors import to_rgba
        for color in colors:
            rgba = to_rgba(color)
            assert len(rgba) == 4


class TestInterdictionNodeColors:

    def test_interdiction_node_colors(self, interdiction_drawer):
        colors = interdiction_drawer._get_interdiction_node_colors()
        assert len(colors) == interdiction_drawer.g.number_of_nodes()

    def test_interdicted_nodes_are_red(self, interdiction_drawer):
        colors = interdiction_drawer._get_interdiction_node_colors()
        for node, color in zip(interdiction_drawer.g.nodes(), colors,):
            if interdiction_drawer.node_results[node]["interdicted"]:
                assert color == "red"


class TestDrawingBuilders:

    def test_draw_flow(self, max_flow_drawer, positions):
        fig, ax = plt.subplots()
        max_flow_drawer._draw_flow(pos=positions, ax=ax,)
        assert len(ax.collections) > 0
        plt.close(fig)

    def test_draw_demand(self, max_flow_drawer, positions):
        fig, ax = plt.subplots()
        max_flow_drawer._draw_demand(pos=positions, ax=ax,)
        assert len(ax.collections) > 0
        plt.close(fig)

    def test_draw_cut(self, min_cut_drawer, positions):
        fig, ax = plt.subplots()
        min_cut_drawer._draw_cut(pos=positions, ax=ax,)
        assert len(ax.collections) > 0
        plt.close(fig)

    def test_draw_interdiction(self, interdiction_drawer, positions,):
        fig, ax = plt.subplots()
        interdiction_drawer._draw_interdiction(pos=positions, ax=ax,)
        assert len(ax.collections) > 0
        plt.close(fig)


class TestColorbars:

    def test_add_node_colorbar(self, max_flow_drawer):
        fig, ax = plt.subplots()
        max_flow_drawer._add_node_colorbar(ax, label="Test Node",)
        # Colorbar creates an additional axes on the figure.
        assert len(fig.axes) >= 2
        plt.close(fig)

    def test_add_edge_colorbar(self, max_flow_drawer):
        fig, ax = plt.subplots()
        max_flow_drawer._add_edge_colorbar(ax, label="Test Edge",)
        assert len(fig.axes) >= 2
        plt.close(fig)


class TestLegends:

    def test_add_legend_min_cut(self, min_cut_drawer):
        fig, ax = plt.subplots()
        min_cut_drawer._add_legend(ax)
        assert len(ax.get_legend().legend_handles) > 0
        plt.close(fig)

    def test_add_legend_interdiction(self, interdiction_drawer):
        fig, ax = plt.subplots()
        interdiction_drawer._add_legend(ax)
        assert len(ax.get_legend().legend_handles) > 0
        plt.close(fig)

    def test_add_interdiction_legend(self, interdiction_drawer):
        fig, ax = plt.subplots()
        interdiction_drawer._add_interdiction_legend(ax)
        assert len(ax.get_legend().legend_handles) > 0
        plt.close(fig)


class TestPublicDraw:

    def test_draw_default_max_flow(self, max_flow_drawer):
        max_flow_drawer.draw(
            pos={node: (float(i), 0.0) for i, node in enumerate(max_flow_drawer.g.nodes())},
            figsize=(6, 4),
        )
        plt.close("all")

    def test_draw_default_min_cut(self, min_cut_drawer):
        min_cut_drawer.draw(
            pos={node: (float(i), 0.0) for i, node in enumerate(min_cut_drawer.g.nodes())},
            figsize=(6, 4),
        )
        plt.close("all")

    def test_draw_default_interdiction(self, interdiction_drawer):
        interdiction_drawer.draw(
            pos={node: (float(i), 0.0) for i, node in enumerate(interdiction_drawer.g.nodes())}, 
            figsize=(6, 4),
            )
        plt.close("all")

    def test_draw_explicit_mode(self, max_flow_drawer):
        max_flow_drawer.draw(
            mode="flow", 
            pos={node: (float(i), 0.0) for i, node in enumerate(max_flow_drawer.g.nodes())}, 
            figsize=(6, 4),
            )
        plt.close("all")

    def test_draw_invalid_mode(self, max_flow_drawer):
        with pytest.raises(ValueError, match="Unknown drawing mode",):
           max_flow_drawer.draw(mode="invalid", figsize=(6, 4),)
