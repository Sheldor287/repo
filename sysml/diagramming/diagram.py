import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from itertools import count

class StructuredGraphBuilder:
    def __init__(self, property_offset=(1,0)):
        self.G = nx.DiGraph()
        self.pos = {}
        self.property_offset = property_offset
        self._id_counter = count()

    def return_graph(self):
        return self.G, self.pos

    @staticmethod
    def _midpoint(source_pos, target_pos, fraction=0.5):
        sx, sy = source_pos
        tx, ty = target_pos
        return (sx + fraction * (tx - sx), sy + fraction * (ty - sy))

    def _unique_id(self, base):
        if base not in self.G:
            return base
        while True:
            candidate = f"{base}_{next(self._id_counter)}"
            if candidate not in self.G:
                return candidate

    def add_entity(self, node_id, label=None, pos=(0, 0)):
        self.G.add_node(node_id, label=label or node_id, node_type="entity")
        self.pos[node_id] = pos

    def add_property(self, target_node_id, prop_name, prop_value, prop_pos=None, val_pos=None, value_offset=None):
        """
        Attaches a property to an existing node.
        [Entity] ---> [Property] ---> [Value]
        Defaults:
            Value position = target position + value_offset
            Property position = midpoint(target, value)
        """
        if target_node_id not in self.G:
            raise KeyError(f"Unknown entity: {target_node_id}")
        target_pos = self.pos[target_node_id]
        # Determine value position automatically.
        if val_pos is None:
            dx, dy = (value_offset if value_offset is not None else self.property_offset)
            val_pos = (target_pos[0] + dx, target_pos[1] + dy)
        # Predicate defaults to midpoint.
        if prop_pos is None:
            prop_pos = self._midpoint(target_pos, val_pos)
        prop_id = self._unique_id(f"{target_node_id}_{prop_name}")
        val_id = self._unique_id(f"{target_node_id}_{prop_name}_{prop_value}")
        self.G.add_node(prop_id, label=str(prop_name), node_type="relation")
        self.G.add_node(val_id, label=str(prop_value), node_type="value")
        self.pos[prop_id] = prop_pos
        self.pos[val_id] = val_pos
        self.G.add_edge(target_node_id, prop_id)
        self.G.add_edge(prop_id, val_id)
        return prop_id

    def add_reified_edge( self, source, rel_name, target, rel_pos=None, meta_nodes=None ):
        """
        Creates a reified relation:
        [source] ---> [relation] ---> [target]
        If rel_pos is not supplied, the relation is placed
        halfway between source and target.
        """
        if source not in self.G or target not in self.G:
            raise KeyError("Source and target must already exist.")
        source_pos = self.pos[source]
        target_pos = self.pos[target]
        if rel_pos is None:
            rel_pos = self._midpoint(source_pos, target_pos)
        rel_id = self._unique_id(f"{source}_{rel_name}_{target}")
        self.G.add_node(rel_id, label=str(rel_name), node_type="relation")
        self.pos[rel_id] = rel_pos
        self.G.add_edge(source, rel_id)
        self.G.add_edge(rel_id, target)
        if meta_nodes:
            for meta_rel_name, meta_source_id in meta_nodes:
                if meta_source_id not in self.G:
                    raise KeyError(f"Unknown metadata source: {meta_source_id}")
                meta_pos = self._midpoint(self.pos[meta_source_id], rel_pos)
                meta_rel_id = self._unique_id(f"{meta_source_id}_{meta_rel_name}_{rel_id}")
                self.G.add_node(meta_rel_id, label=str(meta_rel_name), node_type="relation")
                self.pos[meta_rel_id] = meta_pos
                self.G.add_edge(meta_source_id, meta_rel_id)
                self.G.add_edge(meta_rel_id, rel_id)
        return rel_id

    def get_triples(self):
        triples = []
        for subject, relation in self.G.edges():
            if self.G.nodes[relation].get("node_type") != "relation":
                continue
            predicate = self.G.nodes[relation]["label"]
            for obj in self.G.successors(relation):
                if self.G.nodes[obj].get("node_type") == "value":
                    obj = self.G.nodes[obj]["label"]
                triples.append((subject, predicate, obj))
        return triples

    def draw(self, title=None, figsize=(10, 6), x_margin=0.2, y_margin=0.2, node_size=9, relation_offset=12):
        G, pos = self.return_graph()
        fig, ax = plt.subplots(figsize=figsize)

        STYLE_MAP = {
            "entity": dict( facecolor="skyblue", edgecolor="black", linewidth=1.5, weight="bold", color="black" ),
            "value": dict( facecolor="#e1f5fe", edgecolor="#0288d1", linewidth=1.2, weight="bold", color="#01579b" ),
            "relation": dict( facecolor="white", edgecolor="white", linewidth=0, weight="normal", color="red" ),
        }

        # Establish consistent limits before rendering.
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        xrange = max(xmax - xmin, 1.0)
        yrange = max(ymax - ymin, 1.0)
        ax.set_xlim(xmin - xrange * x_margin, xmax + xrange * x_margin)
        ax.set_ylim(ymin - yrange * y_margin, ymax + yrange * y_margin)
        # Render entity and value nodes.
        node_patches = {}
        for n, (x, y) in pos.items():
            n_type = G.nodes[n].get("node_type", "entity")
            style = STYLE_MAP.get(n_type, STYLE_MAP["entity"])
            if n_type == "relation":
                continue
            bbox_props = dict(
                boxstyle="round,pad=0.5,rounding_size=0.3",
                facecolor=style["facecolor"],
                edgecolor=style["edgecolor"],
                linewidth=style["linewidth"]
            )
            txt = ax.text(
                x, y,
                G.nodes[n]["label"],
                size=node_size,
                weight=style["weight"],
                color=style["color"],
                bbox=bbox_props,
                zorder=3,
                ha="center",
                va="center"
            )
            node_patches[n] = txt.get_bbox_patch()
        # Render relation nodes.
        relation_texts = {}
        for n, (x, y) in pos.items():
            if G.nodes[n].get("node_type") != "relation":
                continue
            txt = ax.annotate(
                G.nodes[n]["label"],
                xy=(x, y),
                xycoords="data",
                xytext=(0, 0),
                textcoords="offset points",
                ha="center",
                va="center",
                size=node_size,
                weight="normal",
                color="red",
                zorder=4
            )
            relation_texts[n] = txt
        # Automatically separate overlapping predicate labels.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        occupied = []
        offsets = [(0, 0)]
        for i in range(1, 10):
            offsets.extend([(0, i * relation_offset), (0, -i * relation_offset)])
        for txt in relation_texts.values():
            for offset in offsets:
                txt.set_position(offset)
                fig.canvas.draw()
                bbox = txt.get_window_extent(renderer)
                overlaps = any(bbox.overlaps(existing) for existing in occupied)
                if not overlaps:
                    occupied.append(bbox)
                    break
        # Draw edges.
        for u, v in G.edges():
            u_type = G.nodes[u].get("node_type")
            v_type = G.nodes[v].get("node_type")
            arrowstyle = ("-|>" if u_type == "relation" and v_type != "relation" else "-")
            arrow = mpatches.FancyArrowPatch(
                pos[u],
                pos[v],
                patchA=node_patches.get(u),
                patchB=node_patches.get(v),
                shrinkA=5 if u in node_patches else 0,
                shrinkB=8 if v in node_patches else 0,
                arrowstyle=arrowstyle,
                mutation_scale=15,
                color="black",
                alpha=0.6,
                zorder=2
            )
            ax.add_patch(arrow)
        # Formatting.
        ax.axis("off")
        if title:
            ax.set_title(title, weight="bold")
        fig.tight_layout()
        plt.show()

if __name__ == "__main__":
    builder = StructuredGraphBuilder()
    # Primary RDF
    builder.add_entity("user", label="user", pos=(-1, 0))
    builder.add_entity("document", label="document", pos=(1, 0))
    hasOwnership_rel_id = builder.add_reified_edge(source="user", rel_name="hasOwnership", target="document", rel_pos=(0, 0),)
    builder.draw('Resource Description Framework (RDF)', figsize=(10, 5))