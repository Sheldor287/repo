import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import matplotlib as mpl
import networkx as nx
import numpy as np

class GraphDrawer:

    DRAWING_CONFIG = {
        'flow': {'builder': '_draw_flow', 'models': {'max_flow'},},
        'residual': {'builder': '_draw_residual', 'models': {'max_flow'},},
        'demand': {'builder': '_draw_demand', 'models': {'max_flow'},},
        'cost': {'builder': '_draw_cost', 'models': {'max_flow'},},
        'cut': {'builder': '_draw_cut', 'models': {'min_cut', 'node_interdiction'},},
        'interdiction': {'builder': '_draw_interdiction', 'models': {'node_interdiction'},},
        }
    DEFAULT_DRAWING_MODE = {
        'max_flow': 'flow',
        'min_cut': 'cut',
        'node_interdiction': 'interdiction',
    }
    colormap = lambda cm,x,y: mcolors.LinearSegmentedColormap.from_list("", cm(np.linspace(x, y, 256)))
    int_cm = lambda x, y: mcolors.LinearSegmentedColormap.from_list("custom_cmap", [x,y])

    CMAPS = {
        'flow': colormap(plt.cm.gist_earth_r, 0.5, 0.9),
        'residual': colormap(plt.cm.gist_earth_r, 0.5, 0.9),
        'demand': colormap(plt.cm.gist_earth_r, 0.5, 0.9),
        'cost': colormap(plt.cm.gist_earth_r, 0.5, 0.9),
        'cut': int_cm("#0077ff", "#ffc400"),
        'interdiction': int_cm("#0077ff", "#ffc400"),
        }

    def __init__(self, solver, node_size=500, cut_color='#ff0000'):
        self.solver = solver
        self.lp = solver.lp
        self.g = solver.g
        self.model = solver.model
        self.model_type = solver.model_type
        self.node_size=node_size
        self.cut_color = cut_color

        self.node_results = solver.get_node_results()
        self.edge_results = solver.get_edge_results()
        self.metrics = solver.get_metrics()

        self.cmap = mcolors.LinearSegmentedColormap.from_list(
            "edge_cmap",plt.cm.gist_earth_r(np.linspace(0.05, 0.90, 256))
        )

    def draw(self, mode=None, pos=None, figsize=(24, 8), **kwargs):
        if mode is None:
            mode = self.DEFAULT_DRAWING_MODE[self.model_type]
        self._validate_mode(mode)
        config = self.DRAWING_CONFIG[mode]
        self.cmap = self.CMAPS[mode]
        builder = getattr(self, config['builder'])
        if pos is None:
            pos = nx.multipartite_layout(self.g, subset_key="layer")
        fig, ax = plt.subplots(figsize=figsize)
        builder(pos=pos, ax=ax, **kwargs)
        ax.set_axis_off()
        plt.show()

    def _validate_mode(self, mode):
        if mode not in self.DRAWING_CONFIG:
            valid = ", ".join(self.DRAWING_CONFIG)
            raise ValueError(f"Unknown drawing mode '{mode}'. Valid modes: {valid}")
        valid_models = self.DRAWING_CONFIG[mode]['models']
        if self.model_type not in valid_models:
            raise ValueError(
                f"Drawing mode '{mode}' is not available for "
                f"model type '{self.model_type}'. "
                f"Valid models: {', '.join(valid_models)}"
            )

    def _get_flow_node_colors(self):
        colors = []
        for n in self.g.nodes:
            data = self.node_results[n]
            if data['node_type'] != 'transshipment':
                rate = max(0.0, min(1.0, data['satisfaction_rate']))
                colors.append(self.cmap(rate))
            else:
                colors.append("#aaaaaa")
        return colors

    def _get_cut_node_colors(self):
        colors = []
        for n in self.g.nodes:
            alpha = self.node_results[n]['alpha']
            colors.append(self.cmap(alpha))
        return colors
    
    def _get_interdiction_node_colors(self):
        colors = []
        for n in self.g.nodes:
            data = self.node_results[n]
            if data['interdicted']:
                colors.append("red")
            else:
                colors.append(self.cmap(data['alpha']))
        return colors

    def _draw_flow(self, pos, ax=None, **kwargs):
        if ax is None:
            _, ax = plt.subplots()
        edge_widths, edge_colors = [], []
        for u, v in self.g.edges:
            data = self.edge_results[(u, v)]
            utilization = data['utilization']
            edge_widths.append(1 + 2 * utilization)
            if utilization > 0:
                edge_colors.append(self.cmap(utilization))
            else:
                edge_colors.append("#cccccc")
        node_colors = self._get_flow_node_colors()
        nx.draw_networkx_nodes(self.g,pos,node_color=node_colors,node_size=self.node_size,ax=ax)
        nx.draw_networkx_edges(self.g,pos,width=edge_widths,arrows=True,edge_color=edge_colors,ax=ax)
        nx.draw_networkx_labels(self.g,pos,ax=ax,font_weight='bold')
        self._add_edge_colorbar(ax,label="Capacity Utilization")
        self._add_node_colorbar(ax,label="Node Satisfaction Rate")
        ax.set_title("Maximum Flow", weight='bold')

    def _add_node_colorbar(self, ax, label="Node Satisfaction Rate"):
        norm = mpl.colors.Normalize(vmin=0,vmax=1)
        sm = mpl.cm.ScalarMappable(norm=norm,cmap=self.cmap)
        sm.set_array([])
        cbar = ax.figure.colorbar(sm,ax=ax,location="left",pad=0.08,shrink=0.8)
        cbar.set_label(label)

    def _add_edge_colorbar(self, ax, label="Capacity Utilization"):
        norm = mpl.colors.Normalize(vmin=0,vmax=1)
        sm = mpl.cm.ScalarMappable(norm=norm,cmap=self.cmap)
        sm.set_array([])
        cbar = ax.figure.colorbar(sm,ax=ax,location="right",pad=0.02,shrink=0.8)
        cbar.set_label(label)

    def _draw_demand(self, pos, ax=None, **kwargs):
        if ax is None:
            _, ax = plt.subplots()
        node_colors = self._get_flow_node_colors()
        nx.draw_networkx_nodes(self.g,pos,node_color=node_colors,node_size=self.node_size,ax=ax)
        nx.draw_networkx_edges(self.g,pos,arrows=True,ax=ax)
        labels = {}
        for n in self.g.nodes:
            data = self.node_results[n]
            if data['node_type'] == 'demand':
                labels[n] = (
                    f"{n}\n"f"D: {data['demand']:.1f}\nS: {data['demand_satisfied']:.1f}\n"
                    f"U: "f"{data['demand'] - data['demand_satisfied']:.1f}"
                )
            else:
                labels[n] = str(n)
        nx.draw_networkx_labels(self.g,pos,labels=labels,ax=ax,font_weight='bold')
        self._add_node_colorbar(ax,label="Demand Satisfaction Rate")
        ax.set_title("Demand Satisfaction")

    def _draw_cut(self, pos, ax=None, **kwargs):
        if ax is None:
            _, ax = plt.subplots()
        edge_colors, edge_widths, edge_styles = [], [], []
        for u, v in self.g.edges:
            if self.model.artificial_edge[u, v]:
                edge_colors.append("#cccccc")
                edge_widths.append(1)
                edge_styles.append("dashed")
                continue

            data = self.edge_results[(u, v)]
            edge_styles.append('solid')
            if data['in_cut']:
                edge_colors.append(self.cut_color)
                edge_widths.append(4)
            else:
                edge_colors.append("#aaaaaa")
                edge_widths.append(1)
        if self.model_type == 'min_cut':
            node_colors = self._get_cut_node_colors()
        else:
            node_colors = self._get_interdiction_node_colors()
        nx.draw_networkx_nodes(self.g,pos,node_color=node_colors,node_size=self.node_size,ax=ax,)
        for (u,v), color, width, style in zip(self.g.edges, edge_colors, edge_widths, edge_styles):
            nx.draw_networkx_edges(self.g,pos,edgelist=[(u, v)],edge_color=color,width=width,style=style,arrows=True,ax=ax)
        nx.draw_networkx_labels(self.g,pos,ax=ax,font_weight='bold')
        ax.set_title(f"Minimum Cut Capacity: ({self.metrics['cut_capacity']:.2f})", weight='bold')
        self._add_legend(ax)

    def _add_legend(self, ax):
        artificial_edge = mlines.Line2D([],[],color="#aaaaaa",linewidth=1.25,linestyle="--",label="Artificial edge",)
        if self.model_type == 'min_cut':
            cut_edge = mlines.Line2D([],[],color=self.cut_color,linewidth=4,label="Minimum-cut edge",)
            non_cut_edge = mlines.Line2D([],[],color="#aaaaaa",linewidth=1.5,label="Non-cut edge",)
            source_side = mlines.Line2D([],[], marker='o',color='w',markerfacecolor=self.cmap(0.0),markersize=10,label=r"Source side ($\alpha=0$)",)
            sink_side = mlines.Line2D([],[],marker='o',color='w',markerfacecolor=self.cmap(1.0),markersize=10,label=r"Sink side ($\alpha=1$)",)
            handles = [cut_edge,non_cut_edge,artificial_edge,source_side,sink_side,]
        else:
            cut_edge = mlines.Line2D([],[],color=self.cut_color,linewidth=4,label=r"Cut edge ($\theta=1$)",)
            interdicted_edge = mlines.Line2D([],[],color="darkorange",linewidth=2.5,linestyle="--",label=r"Interdiction-affected edge ($\omega_u+\omega_v>0$)",)
            interdicted_cut = mlines.Line2D([],[],color="darkorange",linewidth=5,label=r"Interdiction cut contribution ($z=1$)",)
            non_cut_edge = mlines.Line2D([],[],color="#aaaaaa",linewidth=1.5,label="Non-cut edge",)
            interdicted = mlines.Line2D([],[],marker='o',color='w',markerfacecolor='red',markersize=10,label="Interdicted node",)
            non_interdicted = mlines.Line2D([],[],marker='o',color='w',markerfacecolor=self.cmap(0.0),markersize=10,label="Non-interdicted node",)
            handles = [cut_edge,interdicted_cut,interdicted_edge,non_cut_edge,artificial_edge,interdicted,non_interdicted,]
        ax.legend(handles=handles,loc="best",frameon=True,)

    def _draw_interdiction(self, pos, ax=None, **kwargs):
        if ax is None:
            _, ax = plt.subplots()
        # Nodes
        node_colors = []
        node_linewidths = []
        for n in self.g.nodes:
            data = self.node_results[n]
            if data["interdicted"]:
                # Explicit interdiction decision
                node_colors.append("red")
                node_linewidths.append(1.5)
            elif self.model.artificial_node[n]:
                # Artificial nodes are structural, not decision nodes
                node_colors.append("#dddddd")
                node_linewidths.append(1.0)
            else:
                # alpha indicates cut partition
                node_colors.append(self.cmap(data["alpha"]))
                node_linewidths.append(1.0)
        nx.draw_networkx_nodes(self.g, pos, node_color=node_colors, node_size=self.node_size, linewidths=node_linewidths, ax=ax,)
        # Edges
        artificial_edges = []
        ordinary_edges = []
        cut_edges = []
        interdicted_edges = []
        interdicted_cut_edges = []
        for u, v in self.g.edges:
            data = self.edge_results[(u, v)]
            if data["artificial"]:
                artificial_edges.append((u, v))
            elif data["in_interdicted_cut"]:
                # z = 1:
                # edge actually contributes to interdicted cut objective
                interdicted_cut_edges.append((u, v))
            elif data["endpoint_interdicted"]:
                # Touches an interdicted node, but does not contribute
                # to the resulting cut.
                interdicted_edges.append((u, v))
            elif data["in_cut"]:
                # Ordinary cut edge unaffected by interdiction
                cut_edges.append((u, v))
            else:
                ordinary_edges.append((u, v))
        # Draw in layers so important edges appear on top
        nx.draw_networkx_edges( self.g, pos, edgelist=ordinary_edges, edge_color="#cccccc", width=1.25, alpha=0.55, arrows=True, arrowsize=10, ax=ax, )
        nx.draw_networkx_edges( self.g, pos, edgelist=artificial_edges, edge_color="#aaaaaa", width=1.25, alpha=0.55, style="--", arrows=True, arrowsize=10, ax=ax, )
        # Ordinary cut edges
        nx.draw_networkx_edges( self.g, pos, edgelist=cut_edges, edge_color=self.cut_color, width=3.5, alpha=0.95, arrows=True, arrowsize=11, ax=ax, )
        # Edges incident to an interdicted node
        nx.draw_networkx_edges( self.g, pos, edgelist=interdicted_edges, edge_color="grey", width=2.25, alpha=0.8, style="dashed", arrows=True, arrowsize=10, ax=ax, )
        # Edges actually contributing to interdicted cut
        nx.draw_networkx_edges( self.g, pos, edgelist=interdicted_cut_edges, edge_color="purple", width=5.0, alpha=1.0, arrows=True, arrowsize=12, ax=ax, )
        # Node labels
        node_labels = {}
        for n in self.g.nodes:
            data = self.node_results[n]
            if data["interdicted"]:
                node_labels[n] = ( f"{n}\n" f"Cost: {data['interdiction_cost']:.1f}" )
            elif self.model.artificial_node[n]:
                node_labels[n] = f"{n}\nArtificial"
            else:
                node_labels[n] = str(n)
        nx.draw_networkx_labels( self.g, pos, labels=node_labels, font_size=9, font_weight="bold", ax=ax, )
        # Legend
        self._add_interdiction_legend(ax)
        # Metrics
        cut_capacity = self.metrics["cut_capacity"]
        interdicted_cut_capacity = self.metrics["interdicted_cut_capacity"]
        capacity_removed = self.metrics["capacity_removed"]
        interdiction_cost = self.metrics["interdiction_cost"]
        budget = self.metrics["budget"]
        ax.set_title( 
            "Node Interdiction / Minimum Cut\n" f"Cut Capacity: {cut_capacity:.2f} | " 
            f"Interdiction Cost: {interdiction_cost:.2f} / " f"{budget:.2f} | " 
            f"Interdicted-Cut Capacity: {interdicted_cut_capacity:.2f}", 
            fontsize=14, fontweight="bold", pad=15,
        )
    def _add_interdiction_legend(self, ax):
        cut_edge = mlines.Line2D( [], [], color=self.cut_color, linewidth=4, label="Minimum-cut edge" )
        interdicted_edge = mlines.Line2D( [], [], color="gray", linewidth=2.5, linestyle="--", label="Edge incident to interdicted node" )
        interdicted_cut_edge = mlines.Line2D( [], [], color="purple", linewidth=5, label="Interdicted cut edge" )
        artificial_edge = mlines.Line2D( [], [], color="#aaaaaa", linewidth=1.25, linestyle="--", label="Artificial edge" )
        interdicted_node = mlines.Line2D( [], [], marker="o", color="w", markerfacecolor="red", markersize=10, label="Interdicted node" )
        handles = [ cut_edge, interdicted_edge, interdicted_cut_edge, artificial_edge, interdicted_node, ]
        ax.legend(handles=handles, loc="best", frameon=True)