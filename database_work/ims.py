from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import pandas as pd
import numpy as np
import json

from plotly.colors import sample_colorscale
import plotly.graph_objects as go


class ActivityType(Enum):
    TASK = "task"
    MILESTONE = "milestone"
    SUMMARY = "summary"


class DependencyType(Enum):
    FS = "finish-to-start"
    SS = "start-to-start"
    FF = "finish-to-finish"
    SF = "start-to-finish"


@dataclass
class Activity:
    id: str
    name: str
    wbs: str

    activity_type: ActivityType = ActivityType.TASK

    parent_id: str | None = None

    start: date | None = None
    finish: date | None = None

    duration: int | None = None
    percent_complete: float = 0.0

    predecessors: list[str] = field(default_factory=list)
    successors: list[str] = field(default_factory=list)

    resources: list[str] = field(default_factory=list)

    baseline_start: date | None = None
    baseline_finish: date | None = None


@dataclass
class Dependency:
    predecessor: str
    successor: str
    dependency_type: DependencyType = DependencyType.FS
    lag: int = 0


class IntegratedMasterSchedule:
    """
    Activities dataframe: 
    name             DDL Batch 1
    wbs                  1.1.4.1
    start    2026-11-09 00:00:00
    end      2026-11-13 00:00:00

    Dependencies dataframe:
    suc     1.1.6
    pred    1.1.5
    type       FF
    """

    def __init__(self, activities:pd.DataFrame=None, dependencies:pd.DataFrame=None):
        self.activities = {}
        self.dependencies = {}
        if activities is not None:
            self.load_activities(activities)
        if dependencies is not None:
            self.load_activities(dependencies) 

    def add_activity(self, activity: Activity):
        if activity.id in self.activities:
            raise ValueError(f"Activity already exists: {activity.id}")
        self.activities[activity.id] = activity

    def add_dependency(self, dependency: Dependency):
        if dependency.predecessor not in self.activities:
            raise KeyError(dependency.predecessor)
        if dependency.successor not in self.activities:
            raise KeyError(dependency.successor)
        key = (dependency.predecessor, dependency.successor)
        self.dependencies[key] = dependency
        self.activities[dependency.successor].predecessors.append(dependency.predecessor)
        self.activities[dependency.predecessor].successors.append(dependency.successor)

    def add_group(self, id: str, name: str, wbs: str, parent_id: str | None = None,):
        """Add a summary/group activity."""
        group = Activity(id=id, name=name, wbs=wbs, activity_type=ActivityType.SUMMARY, parent_id=parent_id,)
        self.add_activity(group)
        return group

    def add_activity_to_group(self, activity: Activity, parent_id: str,):
        """Add an activity under an existing group."""
        if parent_id not in self.activities:
            raise KeyError(f"Group does not exist: {parent_id}")
        parent = self.activities[parent_id]
        if parent.activity_type != ActivityType.SUMMARY:
            raise ValueError(f"{parent_id} is not a summary/group activity.")
        activity.parent_id = parent_id
        self.add_activity(activity)
        return activity

    def add_activity(self, activity: Activity):
        if activity.id in self.activities:
            raise KeyError(f"Activity already exists: {activity.id}")
        self.activities[activity.id] = activity
    
    def update_group_dates(self):
        """Calculate summary activity dates from child activities."""

        for activity in self.activities.values():
            if activity.activity_type != ActivityType.SUMMARY:
                continue
            children = [child for child in self.activities.values() if child.parent_id == activity.id]
            if not children:
                continue
            starts = [child.start for child in children if child.start is not None]
            finishes = [child.finish for child in children if child.finish is not None]
            if starts:
                activity.start = min(starts)
            if finishes:
                activity.finish = max(finishes)

    def load_activities(self, df):
        required = {"name", "wbs", "start", "end"}
        missing = required - set(df.columns)

        if missing:
            raise ValueError(f"Missing activity columns: {missing}")

        for _, row in df.iterrows():
            wbs = str(row["wbs"]).strip()

            activity = Activity(
                id=wbs,
                name=str(row["name"]).strip(),
                wbs=wbs,
                start=row["start"],
                finish=row["end"],
            )

            self.add_activity(activity)

    def get_parent_wbs(self, wbs):
        parts = wbs.split(".")
        if len(parts) == 1:
            return None
        return ".".join(parts[:-1]) 

    def load_dependencies(self, dep):
        required = {"successor", "predecessor", "type"}
        missing = required - set(dep.columns)
        if missing:
            raise ValueError(f"Missing dependency columns: {sorted(missing)}")
        for _, row in dep.iterrows():
            dependency_code = str(row["type"]).strip().upper()
            try: 
                dependency_type = DependencyType[dependency_code]
            except KeyError:
                raise ValueError(
                    f"Invalid dependency type: {dependency_code!r}. "
                    f"Expected one of: "
                    f"{list(DependencyType.__members__.keys())}"
                )
            dependency = Dependency(
                predecessor=str(row["predecessor"]),
                successor=str(row["successor"]),
                dependency_type=dependency_type,
            )
            self.add_dependency(dependency)

    def visualize(self, sort_mode="hierarchy", title="Integrated Master Schedule | DRAFT SI2"):
        import plotly.graph_objects as go

        rows = []

        for activity in self.activities.values():
            wbs = str(activity.wbs).strip()

            rows.append({
                "id": activity.id,
                "name": activity.name,
                "wbs": wbs,
                "start": pd.to_datetime(activity.start),
                "finish": pd.to_datetime(activity.finish),
                "percent_complete": activity.percent_complete,
                "layer": len(wbs.split(".")) - 1,
            })

        if not rows:
            raise ValueError("IMS contains no activities to visualize.")

        data = pd.DataFrame(rows)

        # ---------------------------------------------------------
        # Sorting
        # ---------------------------------------------------------

        data["_wbs_sort"] = data["wbs"].apply(
            lambda x: tuple(int(part) for part in x.split("."))
        )

        if sort_mode == "hierarchy":
            data = data.sort_values(by="_wbs_sort", ascending=False)
        elif sort_mode == "layer":
            data = data.sort_values(by=["layer", "_wbs_sort"], ascending=False)
        else:
            raise ValueError("sort_mode must be 'hierarchy' or 'layer'")
        data = (data .drop(columns="_wbs_sort") .reset_index(drop=True))

        # ---------------------------------------------------------
        # Labels
        # ---------------------------------------------------------

        data["label"] = data.apply(lambda r: f"{' ' * r['layer']}{r['wbs']} {r['name']}", axis=1,)

        # ---------------------------------------------------------
        # Duration
        # ---------------------------------------------------------

        data["duration_ms"] = (
            data["finish"] - data["start"]
        ).dt.total_seconds() * 1000

        # ---------------------------------------------------------
        # Figure
        # ---------------------------------------------------------

        layers = sorted(data["layer"].unique())
        fig = go.Figure()
        n_stops = 30  
        stops = np.linspace(0.0, 1.0, n_stops)
        colors = sample_colorscale("Viridis", list(np.linspace(0.2, 1.0, n_stops)))
        viridis_top80 = [[float(s), c] for s, c in zip(stops, colors)]

        for layer in layers:
            layer_data = data[data["layer"] == layer]
            fig.add_trace(
                go.Bar(
                    x=layer_data["duration_ms"],
                    base=layer_data["start"],
                    y=layer_data["label"],
                    orientation="h",
                    marker=dict(color=layer, colorscale=viridis_top80, showscale=False),
                    customdata=layer_data[["id", "wbs", "name", "start", "finish", "layer",]].values,

                    hovertemplate=(
                        "<b>%{customdata[1]}  %{customdata[2]}</b><br>"
                        "Start: %{customdata[3]|%Y-%m-%d}<br>"
                        "Finish: %{customdata[4]|%Y-%m-%d}<br>"
                        "Layer: %{customdata[5]}<br>"
                        "<br>"
                        "<i>Click to expand/collapse</i>"
                        "<extra></extra>"
                    ),

                    showlegend=False,
                )
            )

        fig.update_layout(
            title=title,

            height=max(700, len(data) * 24),
            margin=dict(l=450, r=40, t=100, b=80,),
            barmode="overlay",

            xaxis=dict(
                title="Date",
                type="date",
                tickformat="%b %Y",
                dtick="M1",
                showgrid=True,
            ),

            yaxis=dict(
                title="WBS / Activity",
                autorange=False,
                categoryorder="array",
                categoryarray=data["label"].tolist(),
            ),

            hovermode="closest",
        )

        return fig

    def save_visualization(self, path, sort_mode="hierarchy", title="Integrated Master Schedule | DRAFT SI2"):
        rows = []

        for activity in self.activities.values():
            wbs = str(activity.wbs).strip()

            rows.append({
                "id": activity.id,
                "name": activity.name,
                "wbs": wbs,
                "start": pd.to_datetime(activity.start).isoformat(),
                "finish": pd.to_datetime(activity.finish).isoformat(),
                "percent_complete": activity.percent_complete,
                "layer": len(wbs.split(".")) - 1,
            })

        if not rows:
            raise ValueError("IMS contains no activities to visualize.")

        data_json = json.dumps(rows)

        # ---------------------------------------------------------
        # Initial figure
        # ---------------------------------------------------------

        data = pd.DataFrame(rows)

        data["_wbs_sort"] = data["wbs"].apply(
            lambda x: tuple(int(part) for part in x.split("."))
        )

        if sort_mode == "hierarchy":
            data = data.sort_values("_wbs_sort")

        elif sort_mode == "layer":
            data = data.sort_values(
                by=["layer", "_wbs_sort"]
            )

        else:
            raise ValueError(
                "sort_mode must be 'hierarchy' or 'layer'"
            )

        data = (
            data
            .drop(columns="_wbs_sort")
            .reset_index(drop=True)
        )

        data["label"] = data.apply(
            lambda r:
            "    " * r["layer"]
            + r["wbs"]
            + "  "
            + r["name"],
            axis=1,
        )

        data["duration_ms"] = (
            pd.to_datetime(data["finish"])
            - pd.to_datetime(data["start"])
        ).dt.total_seconds() * 1000

        n_stops = 30  
        stops = np.linspace(0.0, 1.0, n_stops)
        colors = sample_colorscale("Viridis", list(np.linspace(0.2, 1.0, n_stops)))
        viridis_top80 = [[float(s), c] for s, c in zip(stops, colors)]


        fig = go.Figure()

        # Single trace — important for JS redraw
        fig.add_trace(
            go.Bar(
                x=data["duration_ms"],
                base=data["start"],
                y=data["label"],
                orientation="h",

                marker=dict(
                    color=data["layer"],
                    colorscale=viridis_top80,
                    showscale=False,
                ),

                customdata=data[
                    [
                        "id",
                        "wbs",
                        "name",
                        "start",
                        "finish",
                        "percent_complete",
                        "layer",
                    ]
                ].values,

                hovertemplate=(
                    "<b>%{customdata[1]}  %{customdata[2]}</b><br>"
                    "Start: %{customdata[3]|%Y-%m-%d}<br>"
                    "Finish: %{customdata[4]|%Y-%m-%d}<br>"
                    "Layer: %{customdata[6]}<br>"
                    "<br>"
                    "<i>Click to expand/collapse</i>"
                    "<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            title=title,

            height=max(
                700,
                len(data) * 24
            ),

            margin=dict(
                l=450,
                r=40,
                t=100,
                b=80,
            ),

            barmode="overlay",

            xaxis=dict(
                title="Date",
                type="date",
                tickformat="%b %Y",
                dtick="M1",
                showgrid=True,
            ),

            # Bottom → top
            yaxis=dict(
                title="WBS / Activity",
                autorange=False,
                categoryorder="array",
                categoryarray=data["label"].tolist(),
            ),

            hovermode="closest",
        )

        # ---------------------------------------------------------
        # JavaScript
        # ---------------------------------------------------------

        graph_id = "ims_graph"

        post_script = f"""
            const allRows = {data_json};

            let currentSort = "{sort_mode}";
            // Start at the top WBS layer; expand a summary by clicking it.
            let collapsed = new Set(allRows.filter(row => row.layer === 0).map(row => row.wbs));

            let selectedLayer0 = "all";
            let selectedLayer1 = "all";

            const graph = document.getElementById("{graph_id}");


            // =========================================================
            // WBS UTILITIES
            // =========================================================

            function wbsTuple(wbs) {{
                return wbs.split(".").map(Number);
            }}


            function isDescendant(wbs, parent) {{
                return wbs.startsWith(parent + ".");
            }}


            // =========================================================
            // SORTING
            // =========================================================

            function sortRows(rows) {{

                const copy = [...rows];

                copy.sort((a, b) => {{

                    if (currentSort === "layer") {{

                        if (a.layer !== b.layer) {{
                            return a.layer - b.layer;
                        }}
                    }}

                    const aa = wbsTuple(a.wbs);
                    const bb = wbsTuple(b.wbs);

                    for (
                        let i = 0;
                        i < Math.max(aa.length, bb.length);
                        i++
                    ) {{

                        const av = aa[i] ?? -1;
                        const bv = bb[i] ?? -1;

                        if (av !== bv) {{
                            return av - bv;
                        }}
                    }}

                    return 0;
                }});

                return copy;
            }}


            // =========================================================
            // VISIBILITY
            // =========================================================

            function isVisible(row) {{

                // -----------------------------------------------------
                // Layer 0 filter
                // -----------------------------------------------------

                if (selectedLayer0 !== "all") {{

                    // Keep selected Layer 0 item
                    if (
                        row.layer === 0 &&
                        row.wbs === selectedLayer0
                    ) {{
                        // Keep
                    }}

                    // Keep descendants of selected Layer 0 item
                    else if (
                        row.layer > 0 &&
                        isDescendant(row.wbs, selectedLayer0)
                    ) {{
                        // Keep
                    }}

                    else {{
                        return false;
                    }}
                }}


                // -----------------------------------------------------
                // Layer 1 filter
                // -----------------------------------------------------

                if (selectedLayer1 !== "all") {{

                    // Keep the Layer 0 parent
                    if (
                        row.layer === 0 &&
                        isDescendant(selectedLayer1, row.wbs)
                    ) {{
                        // Keep
                    }}

                    // Keep selected Layer 1 item
                    else if (
                        row.wbs === selectedLayer1
                    ) {{
                        // Keep
                    }}

                    // Keep descendants of selected Layer 1 item
                    else if (
                        isDescendant(row.wbs, selectedLayer1)
                    ) {{
                        // Keep
                    }}

                    else {{
                        return false;
                    }}
                }}


                // -----------------------------------------------------
                // Collapse filter
                // -----------------------------------------------------

                for (const parent of collapsed) {{

                    if (isDescendant(row.wbs, parent)) {{
                        return false;
                    }}
                }}

                return true;
            }}


            // =========================================================
            // LABEL
            // =========================================================

            function makeLabel(row) {{

                return (
                    "    ".repeat(row.layer)
                    + row.wbs
                    + "  "
                    + row.name
                );
            }}


            // =========================================================
            // REDRAW
            // =========================================================

            function redraw() {{

                let rows = sortRows(allRows);

                rows = rows.filter(isVisible);

                const labels = rows.map(makeLabel);

                const durations = rows.map(row => {{

                    const start = new Date(row.start);
                    const finish = new Date(row.finish);

                    return finish.getTime() - start.getTime();
                }});

                const bases = rows.map(row => row.start);

                const colors = rows.map(row => row.layer);

                const customdata = rows.map(row => [

                    row.id,
                    row.wbs,
                    row.name,
                    row.start,
                    row.finish,
                    row.percent_complete,
                    row.layer

                ]);


                // -----------------------------------------------------
                // Redraw the entire trace
                // -----------------------------------------------------

                Plotly.react(
                    graph,
                    [
                        {{
                            type: "bar",

                            x: durations,

                            base: bases,

                            y: labels,

                            orientation: "h",

                            marker: {{
                                color: colors,
                                colorscale: "Viridis",
                                showscale: false
                            }},

                            customdata: customdata,

                            hovertemplate:
                                "<b>%{{customdata[1]}}  %{{customdata[2]}}</b><br>" +
                                "Start: %{{customdata[3]}}<br>" +
                                "Finish: %{{customdata[4]}}<br>" +
                                "Complete: %{{customdata[5]}}%<br>" +
                                "Layer: %{{customdata[6]}}<br>" +
                                "<br>" +
                                "<i>Click to expand/collapse</i>" +
                                "<extra></extra>"
                        }}
                    ],
                    {{
                        title: {json.dumps(title)},

                        height: Math.max(
                            700,
                            rows.length * 24
                        ),

                        margin: {{
                            l: 450,
                            r: 40,
                            t: 100,
                            b: 80
                        }},

                        barmode: "overlay",

                        xaxis: {{
                            title: "Date",
                            type: "date",
                            tickformat: "%b %Y",
                            dtick: "M1",
                            showgrid: true
                        }},

                        yaxis: {{
                            title: "WBS / Activity",

                            categoryorder: "array",

                            categoryarray: labels,

                            // Bottom → top
                            autorange: "reversed"
                        }},

                        hovermode: "closest"
                    }},

                    {{
                        responsive: true
                    }}
                );
            }}


            // =========================================================
            // CLICK TO COLLAPSE / EXPAND
            // =========================================================

            graph.on("plotly_click", function(event) {{

                const point = event.points[0];

                if (!point || !point.customdata) {{
                    return;
                }}

                const wbs = point.customdata[1];


                // Determine whether this activity has children
                const hasChildren = allRows.some(
                    row => isDescendant(row.wbs, wbs)
                );

                if (!hasChildren) {{
                    return;
                }}


                // Toggle collapsed state
                if (collapsed.has(wbs)) {{

                    collapsed.delete(wbs);

                }} else {{

                    collapsed.add(wbs);
                }}

                redraw();
            }});


            // =========================================================
            // CONTROLS
            // =========================================================

            const container = graph.parentElement;

            const controls = document.createElement("div");

            controls.style.marginBottom = "10px";
            controls.style.fontFamily = "Arial, sans-serif";


            // =========================================================
            // BUILD LAYER 0 OPTIONS
            // =========================================================

            const layer0Rows = allRows
                .filter(row => row.layer === 0)
                .sort((a, b) => {{

                    const aa = wbsTuple(a.wbs);
                    const bb = wbsTuple(b.wbs);

                    return aa[0] - bb[0];
                }});


            let layer0Options = `
                <option value="all">
                    All
                </option>
            `;

            for (const row of layer0Rows) {{

                layer0Options += `
                    <option value="${{row.wbs}}">
                        ${{row.wbs}} ${{row.name}}
                    </option>
                `;
            }}


            // =========================================================
            // BUILD LAYER 1 OPTIONS
            // =========================================================

            function buildLayer1Options(layer0) {{

                let layer1Rows = allRows
                    .filter(row => row.layer === 1);


                // If Layer 0 is selected,
                // only show its children.
                if (layer0 !== "all") {{

                    layer1Rows = layer1Rows.filter(
                        row => isDescendant(row.wbs, layer0)
                    );
                }}


                layer1Rows.sort((a, b) => {{

                    const aa = wbsTuple(a.wbs);
                    const bb = wbsTuple(b.wbs);

                    for (
                        let i = 0;
                        i < Math.max(aa.length, bb.length);
                        i++
                    ) {{

                        const av = aa[i] ?? -1;
                        const bv = bb[i] ?? -1;

                        if (av !== bv) {{
                            return av - bv;
                        }}
                    }}

                    return 0;
                }});


                let options = `
                    <option value="all">
                        All
                    </option>
                `;


                for (const row of layer1Rows) {{

                    options += `
                        <option value="${{row.wbs}}">
                            ${{row.wbs}} ${{row.name}}
                        </option>
                    `;
                }}

                return options;
            }}


            // =========================================================
            // CREATE CONTROLS
            // =========================================================

            controls.innerHTML = `
                <label>
                    <b>Layer 0:</b>

                    <select id="ims-layer0">
                        ${{layer0Options}}
                    </select>
                </label>

                &nbsp;&nbsp;

                <label>
                    <b>Layer 1:</b>

                    <select id="ims-layer1">
                        ${{buildLayer1Options("all")}}
                    </select>
                </label>

                &nbsp;&nbsp;

                <label>
                    <b>Sort:</b>

                    <select id="ims-sort">
                        <option value="hierarchy">
                            WBS Hierarchy
                        </option>

                        <option value="layer">
                            Layer
                        </option>
                    </select>
                </label>

                &nbsp;&nbsp;

                <button id="ims-top">
                    Show Top Layer
                </button>

                <button id="ims-expand">
                    Expand All
                </button>
            `;

            container.insertBefore(
                controls,
                graph
            );


            // =========================================================
            // LAYER 0 CONTROL
            // =========================================================

            const layer0Select =
                controls.querySelector("#ims-layer0");

            layer0Select.value = "all";

            layer0Select.addEventListener(
                "change",
                function() {{

                    selectedLayer0 = this.value;

                    // Rebuild Layer 1 based on selected Layer 0
                    const layer1Select =
                        controls.querySelector("#ims-layer1");

                    layer1Select.innerHTML =
                        buildLayer1Options(selectedLayer0);

                    // Reset Layer 1
                    selectedLayer1 = "all";

                    layer1Select.value = "all";

                    // Reset collapse state
                    collapsed.clear();

                    redraw();
                }}
            );


            // =========================================================
            // LAYER 1 CONTROL
            // =========================================================

            const layer1Select =
                controls.querySelector("#ims-layer1");

            layer1Select.value = "all";

            layer1Select.addEventListener(
                "change",
                function() {{

                    selectedLayer1 = this.value;

                    // Reset collapse state
                    collapsed.clear();

                    redraw();
                }}
            );


            // =========================================================
            // SORT CONTROL
            // =========================================================

            const sortSelect =
                controls.querySelector("#ims-sort");

            sortSelect.value = currentSort;

            sortSelect.addEventListener(
                "change",
                function() {{

                    currentSort = this.value;

                    redraw();
                }}
            );


            // =========================================================
            // TOP LAYER / EXPAND ALL
            // =========================================================

            controls.querySelector("#ims-top").addEventListener("click", function() {{
                collapsed = new Set(allRows.filter(row => row.layer === 0).map(row => row.wbs));
                redraw();
            }});

            controls
                .querySelector("#ims-expand")
                .addEventListener(
                    "click",
                    function() {{

                        collapsed.clear();

                        redraw();
                    }}
                );


            // =========================================================
            // INITIAL VIEW
            // =========================================================

            redraw();
            """

        # ---------------------------------------------------------
        # Write HTML
        # ---------------------------------------------------------

        fig.write_html(
            path,
            include_plotlyjs=True,
            full_html=True,
            div_id=graph_id,
            post_script=post_script,
        )

    @staticmethod
    def _normalize_wbs(value):
        if pd.isna(value):
            raise ValueError("WBS identifier cannot be null")

        # Excel/pandas may read 2 as 2.0
        if isinstance(value, float) and value.is_integer():
            return str(int(value))

        return str(value).strip()

if __name__ == '__main__':
    from pathlib import Path
    import argparse
    parser = argparse.ArgumentParser(description="Convert an XL file to an IMS.")
    parser.add_argument("input", help="Path to the XLSX file")
    parser.add_argument("-o", "--output", help="Path to the output HTML")
    parser.add_argument(
        "-a", "--activity", default="activity", help="Activity sheet name"
    )
    parser.add_argument(
        "-d", "--dependencies", default="dependencies", help="Dependency sheet name"
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        raise FileNotFoundError(f"Excel file not found: {input_file}")

    output_file = (
        input_file.with_suffix(".html")
        if args.output is None
        else Path(args.output)
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    act = pd.read_excel(input_file, sheet_name=args.activity)
    dep = pd.read_excel(input_file, sheet_name=args.dependencies)

    ims = IntegratedMasterSchedule()
    ims.load_activities(act)
    ims.load_dependencies(dep)
    ims.save_visualization(
        output_file,
        sort_mode="hierarchy",
        title="Integrated Master Schedule | DRAFT SI2",
    )





