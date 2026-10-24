import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

class StructuredGraphBuilder:
    def __init__(self):
        self.G = nx.DiGraph()
        self.pos = {}

    def return_graph(self):
        return self.G, self.pos

    def add_entity(self, node_id, label=None, pos=(0, 0)):
        self.G.add_node(node_id, label=label or node_id, node_type="entity")
        self.pos[node_id] = pos

    def add_property(self, target_node_id, prop_name, prop_value, prop_pos=None, val_pos=None ):
        """
        Attaches a property to any existing node.

        [Target Node] --- [property] ---> [value]

        If prop_pos is not supplied, it is placed halfway between
        the target node and the value node.
        """
        prop_id = f"{target_node_id}_{prop_name}"
        val_id = f"{target_node_id}_{prop_name}_{prop_value}"
        self.G.add_node( prop_id, label=prop_name, node_type="relation" )
        self.G.add_node( val_id, label=str(prop_value), node_type="value" )

        # Value position must be supplied because it determines
        # the direction/extent of the property.
        if val_pos is None:
            raise ValueError( "val_pos must be specified when adding a property." )
        # Default property position = midpoint of target and value
        if prop_pos is None:
            target_pos = self.pos[target_node_id]
            prop_pos = ( (3*target_pos[0] + 2*val_pos[0])/5, (3*target_pos[1] + 2*val_pos[1])/5 )

        self.pos[prop_id] = prop_pos
        self.pos[val_id] = val_pos

        self.G.add_edge(target_node_id, prop_id)
        self.G.add_edge(prop_id, val_id)

    def add_reified_edge( self, source, rel_name, target, rel_pos=None, meta_nodes=None ):
        """
        Creates a reified relation:

        [source] ---> [relation] ---> [target]

        If rel_pos is not supplied, the relation is placed
        halfway between source and target.
        """

        source_pos = self.pos[source]
        target_pos = self.pos[target]
        # Default relation position = midpoint
        if rel_pos is None:
            rel_pos = ( (3*source_pos[0] + 2*target_pos[0])/5, (3*source_pos[1] + 2*target_pos[1])/5 )

        rel_id = f"{source}_{rel_name}_{target}"
        self.G.add_node( rel_id, label=rel_name, node_type="relation" )
        self.pos[rel_id] = rel_pos
        self.G.add_edge(source, rel_id)
        self.G.add_edge(rel_id, target)

        if meta_nodes:
            for meta_rel_name, meta_source_id in meta_nodes:
                meta_rel_id = ( f"{meta_source_id}_{meta_rel_name}_{rel_id}" )
                mx = ( 2*self.pos[meta_source_id][0] + rel_pos[0] ) / 3
                my = ( 2*self.pos[meta_source_id][1] + rel_pos[1] ) / 3
                self.G.add_node( meta_rel_id, label=meta_rel_name, node_type="relation" )
                self.pos[meta_rel_id] = (mx, my)
                self.G.add_edge(meta_source_id, meta_rel_id)
                self.G.add_edge(meta_rel_id, rel_id)

        return rel_id

    def get_triples(self):
        G,_ = self.return_graph()
        triples = []
        for subject, relation in G.edges():
            if G.nodes[relation].get("node_type") != "relation":
                continue
            predicate = G.nodes[relation]["label"]
            for obj in G.successors(relation):
                if G.nodes[obj].get("node_type") == "value":
                    obj = G.nodes[obj]["label"]
                triples.append( (subject, predicate, obj) )
        return triples

    def draw(self, title=None, figsize=(10, 6), x_margin=0.5, y_margin=0.5):
        G, pos = self.return_graph()
        fig, ax = plt.subplots(figsize=figsize)

        STYLE_MAP = {
            "entity": dict( facecolor="skyblue", edgecolor="black", linewidth=1.5, weight="bold", color="black" ),
            "value": dict( facecolor="#e1f5fe", edgecolor="#0288d1", linewidth=1.2, weight="bold", color="#01579b" ),
            "relation": dict( facecolor="white", edgecolor="white", linewidth=0, weight="normal", color="red" ),
        }

        node_patches = {}
        text_objects = {}

        # Render nodes
        for n, (x, y) in pos.items():

            n_type = G.nodes[n].get("node_type", "entity")
            style = STYLE_MAP.get(n_type, STYLE_MAP["entity"])
            bbox_props = dict( boxstyle="round,pad=0.5,rounding_size=0.3", facecolor=style["facecolor"], edgecolor=style["edgecolor"], linewidth=style["linewidth"] )
            txt = ax.text( x, y, G.nodes[n]["label"], size=9, weight=style["weight"], color=style["color"], bbox=bbox_props, zorder=3, ha="center", va="center" )
            text_objects[n] = txt
            node_patches[n] = txt.get_bbox_patch()

        # Render edges
        for u, v in G.edges():

            u_type = G.nodes[u].get("node_type")
            v_type = G.nodes[v].get("node_type")
            arrowstyle = "-"

            if u_type == "relation" and v_type != "relation":
                arrowstyle = "-|>"

            arrow = mpatches.FancyArrowPatch(
                pos[u], pos[v], patchA=node_patches[u], patchB=node_patches[v],
                shrinkA=5, shrinkB=8, arrowstyle=arrowstyle,
                mutation_scale=15, color="black", alpha=0.6, zorder=3
            )
            ax.add_patch(arrow)

        # First-pass limits based on positions
        xs = [x for x, y in pos.values()]
        ys = [y for x, y in pos.values()]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        x_range = max(xmax - xmin, 1)
        y_range = max(ymax - ymin, 1)
        ax.set_xlim( xmin - x_range * 0.25, xmax + x_range * 0.25 )
        ax.set_ylim( ymin - y_range * 0.25, ymax + y_range * 0.25 )

        # Force Matplotlib to calculate text bounding boxes
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        # Determine actual rendered bounds
        data_boxes = []
        for txt in text_objects.values():
            bbox = txt.get_window_extent(renderer=renderer)
            # Convert display coordinates -> data coordinates
            corners = ax.transData.inverted().transform([ [bbox.x0, bbox.y0], [bbox.x1, bbox.y1] ])
            data_boxes.append(corners)

        # Actual object bounds
        actual_xmin = min(box[0][0] for box in data_boxes)
        actual_xmax = max(box[1][0] for box in data_boxes)
        actual_ymin = min(box[0][1] for box in data_boxes)
        actual_ymax = max(box[1][1] for box in data_boxes)

        # Add symmetric margins around ACTUAL rendered bounds
        ax.set_xlim( actual_xmin - x_margin, actual_xmax + x_margin )
        ax.set_ylim( actual_ymin - y_margin, actual_ymax + y_margin )

        # Formatting
        ax.axis("off")
        if title:
            ax.set_title(title, weight="bold")
        plt.show()

if __name__ == "__main__":
    builder = StructuredGraphBuilder()
    # Primary RDF
    builder.add_entity("user", label="user", pos=(-1, 0))
    builder.add_entity("document", label="document", pos=(1, 0))
    hasOwnership_rel_id = builder.add_reified_edge(source="user", rel_name="hasOwnership", target="document", rel_pos=(0, 0),)
    builder.draw('Resource Description Framework (RDF)', figsize=(10, 5))