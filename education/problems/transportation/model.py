import networkx as nx
import numpy as np
from pyomo import environ as pyo
import json 


class TransportationProblem:
    def __init__(self, plants=3, warehouses=5, cost_range=(1, 10), capacity_range=(10, 100), demand_range=(10, 100), total_demand=None):
        self.plants = plants
        self.warehouses = warehouses
        self.cost_range = cost_range
        self.capacity_range = capacity_range
        self.demand_range = demand_range
        self.total_demand = np.random.randint(*self.demand_range) if total_demand is None else total_demand
        self.graph = self.create_transportation()
        self.colors = ['lightblue' if self.graph.nodes[n]['type']=='plant' else 'lightgreen' for n in self.graph.nodes()]
        self.pos = nx.bipartite_layout(self.graph, nodes=[n for n in self.graph.nodes() if self.graph.nodes[n]['type']=='plant'])

    def _assign_demand(self):
        return np.random.multinomial(self.total_demand, [1/self.warehouses]*self.warehouses)

    def _assign_capacity(self):
        return np.random.multinomial(self.total_demand, [1/self.plants]*self.plants)

    def create_transportation(self) -> nx.DiGraph:
        G = nx.DiGraph()
        capacities = self._assign_capacity()
        demands = self._assign_demand()
        for i in range(self.plants):
            G.add_node(f"Plant {i+1}", type="plant", capacity=capacities[i])
        for j in range(self.warehouses):
            G.add_node(f"Warehouse {j+1}", type="warehouse", demand=demands[j])
        for i in range(self.plants):
            for j in range(self.warehouses):
                cost = np.random.randint(*self.cost_range)
                G.add_edge(f"Plant {i+1}", f"Warehouse {j+1}", cost=cost)
        return G


class TransportationLP:
    def __init__(self, transportation_problem):
        self.tp = transportation_problem
        self.G = self.tp.graph

        self.capacities = {n: self.G.nodes[n]['capacity'] for n in self.G.nodes() if self.G.nodes[n]['type'] == 'plant'}
        self.demands = {n: self.G.nodes[n]['demand'] for n in self.G.nodes() if self.G.nodes[n]['type'] == 'warehouse'}
        self.costs = {(u, v): self.G.edges[u, v]['cost'] for u, v in self.G.edges()}

        self.model = None
        self.solver = pyo.SolverFactory("appsi_highs")
        self.results = None

    def create_model(self):
        # Model Initialized
        model = pyo.ConcreteModel()
        # Sets
        model.plants = pyo.Set(initialize=list(self.capacities.keys()))
        model.warehouses = pyo.Set(initialize=list(self.demands.keys()))
        model.edges = pyo.Set(initialize=list(self.costs.keys()), dimen=2)
        # Parameters
        model.capacities = pyo.Param(model.plants, initialize=self.capacities)
        model.demands = pyo.Param(model.warehouses, initialize=self.demands)
        model.costs = pyo.Param(model.edges, initialize=self.costs)
        # Decision variables
        model.x = pyo.Var(model.edges, domain=pyo.NonNegativeReals)
        # Objective
        model.objective = pyo.Objective(expr=sum(model.costs[e] * model.x[e] for e in model.edges), sense=pyo.minimize)

        # Plant capacity constraints
        def capacity_constraint_rule(model, p):
            return (sum(model.x[e] for e in model.edges if e[0] == p) <= model.capacities[p])
        model.capacity_constraint = pyo.Constraint(model.plants, rule=capacity_constraint_rule)

        # Warehouse demand constraints
        def demand_constraint_rule(model, w):
            return (sum(model.x[e] for e in model.edges if e[1] == w) >= model.demands[w])
        model.demand_constraint = pyo.Constraint(model.warehouses, rule=demand_constraint_rule)

        self.model = model
        return model

    def solve(self):
        self.model = self.create_model()
        self.results = self.solver.solve(self.model)
        return self.model, self.results

    def export_solution(self, path="problems/transportation/solution.json"):
        if self.model is None:
            self.solve()
        model = self.model
        solution = {
            "plants": [{"id": p, "capacity": float(self.capacities[p]),} for p in model.plants],
            "warehouses": [{"id": w, "demand": float(self.demands[w]),} for w in model.warehouses],
            "edges": [{"source": e[0], "target": e[1], "cost": float(self.costs[e]), "flow": float(pyo.value(model.x[e])),} for e in model.edges],
            "objective": float(pyo.value(model.objective)),
        }
        if path is not None:
            with open(path, "w") as f:
                json.dump(solution, f, indent=4)
        return solution

