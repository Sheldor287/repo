import pyomo.environ as pyo
import networkx as nx

def standard_min_cost_flow(H):

    # Compute supply/demand imbalance
    total_supply = sum(H.nodes[n]['demand'] for n in H.nodes() if H.nodes[n]['demand'] < 0)
    total_demand = sum(H.nodes[n]['demand'] for n in H.nodes() if H.nodes[n]['demand'] > 0)
    imbalance = total_supply + total_demand

    max_layer = max(H.nodes[n]['layer'] for n in H.nodes())

    #  Add artificial nodes
    if imbalance > 0:
        # More demand
        H.add_node('dS', demand=-imbalance, layer=-1)

        for n in H.nodes():
            if H.nodes[n].get('layer') == max_layer:
                H.add_edge('dS', n, cost=0, capacity=imbalance)

    elif imbalance < 0:
        # More supply
        H.add_node('dT', demand=-imbalance, layer=-1)

        for n in H.nodes():
            if H.nodes[n].get('layer') == 0:
                H.add_edge(n, 'dT', cost=0, capacity=-imbalance)

    """ Build model """
    model = pyo.ConcreteModel()

    model.nodes = pyo.Set(initialize=list(H.nodes()))
    model.edges = pyo.Set(initialize=list(H.edges()), dimen=2)

    model.cost = pyo.Param(model.edges,initialize={(u, v): H.edges[u, v]['cost'] for u, v in H.edges()})
    model.capacity = pyo.Param(model.edges,initialize={(u, v): H.edges[u, v]['capacity'] for u, v in H.edges()})
    model.demand = pyo.Param(model.nodes,initialize={n: H.nodes[n]['demand'] for n in H.nodes()})

    # Vars
    model.x = pyo.Var(model.edges, within=pyo.NonNegativeReals)

    # Objective
    model.obj = pyo.Objective(expr=sum(model.cost[u, v] * model.x[u, v] for (u, v) in model.edges),sense=pyo.minimize)

    # Constraints
    def cap_rule(m, u, v):
        return m.x[u, v] <= m.capacity[u, v]
    model.cap = pyo.Constraint(model.edges, rule=cap_rule)


    def flow_rule(m, n):
        inflow = sum(m.x[u, v] for (u, v) in m.edges if v == n)
        outflow = sum(m.x[u, v] for (u, v) in m.edges if u == n)
        return inflow - outflow == m.demand[n]

    model.flow = pyo.Constraint(model.nodes, rule=flow_rule)

    # Solve
    solver = pyo.SolverFactory('appsi_highs')
    result = solver.solve(model)

    flow_dict = {(u, v): pyo.value(model.x[u, v]) for (u, v) in model.edges}
    return result, flow_dict