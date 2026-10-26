
import numpy as np
import pandas as pd

def estimate_joint_pmf(df, horizon, nodes=None):
    """
    Estimate the time-weighted joint PMF of binary node states.

    Parameters
    ----------
    df : pandas.DataFrame
        Columns: node, time, state.
        Each row records a node state change. Include initial states
        at time 0 for every node.
    horizon : float
        End of the observation window. Must exceed the final event time.
    nodes : sequence, optional
        Node ordering for joint-state tuples.

    Returns
    -------
    trajectory : DataFrame
        Intervals, joint states, and interval durations.
    joint_pmf : DataFrame
        Joint-state probabilities and time spent in each state.
    marginal_pmf : DataFrame
        Estimated probability of each node being active/inactive.
    """
    required = {"node", "time", "state"}
    if not required.issubset(df.columns):
        raise ValueError(f"Data must contain columns {required}")
    events = df.copy()
    events["time"] = pd.to_numeric(events["time"])
    events["state"] = pd.to_numeric(events["state"])
    if events.empty:
        raise ValueError("Event data cannot be empty.")
    if not np.isfinite(events["time"]).all():
        raise ValueError("Event times must be finite.")
    if not events["state"].isin([0, 1]).all():
        raise ValueError("States must be binary (0 or 1).")
    if (events["time"] < 0).any():
        raise ValueError("Event times cannot be negative.")
    if nodes is None:
        nodes = sorted(events["node"].unique())
    else:
        nodes = list(nodes)
    if len(set(nodes)) != len(nodes):
        raise ValueError("Node labels must be unique.")
    if set(events["node"]) != set(nodes):
        raise ValueError("The node list must match the event data.")
    events = events.sort_values("time", kind="stable")
    if horizon <= events["time"].max():
        raise ValueError("horizon must exceed the final event time.")
    initial = events.loc[events["time"] == 0]
    if set(initial["node"]) != set(nodes):
        raise ValueError("Provide an initial state at time 0 for every node.")
    if initial["node"].duplicated().any():
        raise ValueError("Each node must have exactly one initial state.")
    # Initialize the complete network state.
    state = initial.set_index("node")["state"].to_dict()
    state = {node: int(state[node]) for node in nodes}
    trajectory = []
    previous_time = 0.0
    # Process all events at the same timestamp together.
    later_events = events.loc[events["time"] > 0]
    for time, group in later_events.groupby("time", sort=True):
        if time > previous_time:
            trajectory.append({"start": previous_time, "end": float(time), "duration": float(time - previous_time), "joint_state": tuple(state[node] for node in nodes),})
        # Apply observations; repeated states are allowed.
        for _, event in group.iterrows():
            node = event["node"]
            state[node] = int(event["state"])
        previous_time = float(time)
    # The last observed state persists through the specified horizon.
    trajectory.append(
        {"start": previous_time, "end": float(horizon), "duration": float(horizon - previous_time), "joint_state": tuple(state[node] for node in nodes),}
        )
    trajectory = pd.DataFrame(trajectory)
    # Time-weighted joint PMF.
    joint_pmf = (trajectory.groupby("joint_state", as_index=False)["duration"] .sum() .rename(columns={"duration": "time_in_state"}))
    joint_pmf["probability"] = (joint_pmf["time_in_state"] / float(horizon))
    joint_pmf["state_label"] = joint_pmf["joint_state"].map(lambda x: "".join(map(str, x)))
    joint_pmf = joint_pmf.sort_values("probability", ascending=False).reset_index(drop=True)
    # Marginal PMFs derived from the reconstructed trajectory.
    marginal_rows = []
    for i, node in enumerate(nodes):
        p_active = sum(row.duration for row in trajectory.itertuples() if row.joint_state[i] == 1) / float(horizon)
        marginal_rows.append({"node": node, "P_active": p_active, "P_inactive": 1.0 - p_active,})
    marginal_pmf = pd.DataFrame(marginal_rows)
    return trajectory, joint_pmf, marginal_pmf

"""
trajectory, joint_pmf, marginal_pmf = estimate_joint_pmf(df, horizon=101)

print(trajectory)
print(joint_pmf)
print(marginal_pmf)
"""