import pyomo.environ as pyo
import networkx as nx

# Objectives & constraints
def mcf_obj(m):
    return sum(m.cost[u, v] * m.x[u, v] for (u, v) in m.edges)

def mf_obj(m):
    S = [n for n in m.nodes if m.demand < 0]
    T = [n for n in m.nodes if m.demand > 0]
    outflow = sum(sum(m.x[s, j] for (s2, j) in m.A if s2 == s) for s in S)
    inflow = sum(sum(m.x[i, t] for (i, t2) in m.A if t2 == t) for t in T)
    return outflow - inflow

def edge_cap_rule(m, u, v):
    return m.x[u, v] <= m.capacity[u, v]

def edge_flow_rule(m, n):
    inflow = sum(m.x[u, v] for (u, v) in m.edges if v == n)
    outflow = sum(m.x[u, v] for (u, v) in m.edges if u == n)
    return inflow - outflow == m.demand[n]

def preprocess_demand_imbalance(G):
    total_supply = sum(G.nodes[n]['demand'] for n in G.nodes() if G.nodes[n]['demand'] < 0)
    total_demand = sum(G.nodes[n]['demand'] for n in G.nodes() if G.nodes[n]['demand'] > 0)
    imbalance = total_supply + total_demand
    max_layer = max(G.nodes[n]['layer'] for n in G.nodes())

    #  Add artificial nodes
    if imbalance > 0:
        # More demand
        G.add_node('dS', demand=-imbalance, layer=-1)
        for n in G.nodes():
            if G.nodes[n].get('layer') == max_layer:
                G.add_edge('dS', n, cost=0, capacity=imbalance)

    elif imbalance < 0:
        # More supply
        G.add_node('dT', demand=-imbalance, layer=-1)
        for n in G.nodes():
            if G.nodes[n].get('layer') == 0:
                G.add_edge(n, 'dT', cost=0, capacity=-imbalance)
    return G

# MCF
def standard_min_cost_flow(G):
    """ Minimize cost of total travel over the graph """
    # Create artifical nodes if needed
    G = preprocess_demand_imbalance(G)

    # Sets & params
    model = pyo.ConcreteModel()
    model.nodes = pyo.Set(initialize=list(G.nodes()))
    model.edges = pyo.Set(initialize=list(G.edges()), dimen=2)
    model.cost = pyo.Param(model.edges,initialize={(u, v): G.edges[u, v]['cost'] for u, v in G.edges()})
    model.capacity = pyo.Param(model.edges,initialize={(u, v): G.edges[u, v]['capacity'] for u, v in G.edges()})
    model.demand = pyo.Param(model.nodes,initialize={n: G.nodes[n]['demand'] for n in G.nodes()})

    # Vars
    model.x = pyo.Var(model.edges, within=pyo.NonNegativeReals)

    # Objective & constraints 
    model.obj = pyo.Objective(rule=mcf_obj, sense=pyo.minimize)
    model.cap = pyo.Constraint(model.edges, rule=edge_cap_rule)
    model.flow = pyo.Constraint(model.nodes, rule=edge_flow_rule)

    # Solve
    solver = pyo.SolverFactory('appsi_highs')
    result = solver.solve(model)
    flow_dict = {(u, v): pyo.value(model.x[u, v]) for (u, v) in model.edges}
    return result, flow_dict

def standard_max_flow(G):
    """ Maximize total flow over the graph """
    # Create artifical nodes if needed
    G = preprocess_demand_imbalance(G)

    # Sets & params
    model = pyo.ConcreteModel()
    model.nodes = pyo.Set(initialize=list(G.nodes()))
    model.edges = pyo.Set(initialize=list(G.edges()), dimen=2)
    model.capacity = pyo.Param(model.edges,initialize={(u, v): G.edges[u, v]['capacity'] for u, v in G.edges()})
    model.demand = pyo.Param(model.nodes,initialize={n: G.nodes[n]['demand'] for n in G.nodes()})

    # Vars
    model.x = pyo.Var(model.edges, within=pyo.NonNegativeReals)

    # Objective & constraints
    model.obj = pyo.Objective(rule=mf_obj, sense=pyo.maximize)
    model.cap = pyo.Constraint(model.edges, rule=edge_cap_rule)
    model.flow = pyo.Constraint(model.edges, rule=edge_flow_rule)

    # Solve 
    solver = pyo.SolverFactory('appsi_highs')
    result = solver.solve(model)
    flow_dict = {(u, v): pyo.value(model.x[u, v]) for (u, v) in model.edges}
    return result, flow_dict




