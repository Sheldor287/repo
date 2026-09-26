from pyomo import environ as pyo

class Objectives:
    @staticmethod
    def max_flow(m:pyo.ConcreteModel) -> pyo.Objective:
        """Primal maxflow problem"""
        return pyo.Objective(expr=m.F, sense=pyo.maximize)

    @staticmethod
    def min_cut_flow2(m:pyo.ConcreteModel) -> pyo.Objective:
        """Dual maxflow problem"""
        return pyo.Objective(expr=sum(m.capacity[u,v]*m.theta[u,v] for u, v in m.edges), sense=pyo.minimize)

    @staticmethod
    def min_cut_flow(m):
        return pyo.Objective(
            expr=sum(m.capacity[u, v] * m.theta[u, v] for u, v in m.edges if not m.artificial_edge[u, v]),sense=pyo.minimize,
        )

    @staticmethod
    def interdicted_min_cut_flow(m:pyo.ConcreteModel) -> pyo.Objective:
        return pyo.Objective(expr=sum(m.capacity[u,v]*m.z[u,v] for u, v in m.edges), sense=pyo.minimize)

    @staticmethod
    def min_cost_flow(m:pyo.ConcreteModel) -> pyo.Objective:
        """Minimization of the weighted sum of an s-t path"""
        expr = sum(m.cost[u, v] * m.x[u, v] for (u, v) in m.edges)
        return pyo.Objective(expr=expr, sense=pyo.minimize)

    REGISTRY = {
        'max_flow': max_flow,
        'min_cost_flow': min_cost_flow,
        'min_cut': min_cut_flow, 
        'interdicted_min_cut_flow': interdicted_min_cut_flow
        }

    @classmethod
    def apply(cls, problem_type, model):
        try:
            objective = cls.REGISTRY[problem_type]
        except KeyError:
            raise ValueError(f"Unknown objective '{problem_type}'")
        model.obj = objective(model)
        return model

class Rules:
    @staticmethod
    def edge_cap_rule(m:pyo.ConcreteModel, u:pyo.Param, v:pyo.Param,) -> pyo.Constraint:
        """Capacity can be bandwidth, time-requirement, or 1 if assessing count of independent paths"""
        return m.x[u, v] <= m.capacity[u, v] * m.node_state[u] * m.node_state[v] * m.edge_state[u,v]
     
    @staticmethod
    def edge_flow_rule(m:pyo.ConcreteModel, n:pyo.Param) -> pyo.Constraint:
        """Flow out = Flow in for all nodes; originator demand=-1, endpoint demand=1"""
        if n in (m.s, m.t):
            return pyo.Constraint.Skip
        inflow = sum(m.x[u, v] for (u, v) in m.edges if v == n)
        outflow = sum(m.x[u, v] for (u, v) in m.edges if u == n)
        return inflow == outflow
    
    @staticmethod
    def source_flow_rule(m:pyo.ConcreteModel) -> pyo.Constraint:
        """Controls flow from artificial source s"""
        outflow = sum(m.x[u, v] for (u, v) in m.edges if u == m.s)
        inflow = sum(m.x[u, v] for (u, v) in m.edges if v == m.s)
        return outflow - inflow == m.F
    
    @staticmethod
    def sink_flow_rule(m:pyo.ConcreteModel) -> pyo.Constraint:
        """Controls flow to artificial terminus t"""
        inflow = sum(m.x[u, v] for (u, v) in m.edges if v == m.t)
        outflow = sum(m.x[u, v] for (u, v) in m.edges if u == m.t)
        return inflow - outflow == m.F

    @staticmethod
    def cutset_rule(m, u, v):
        """theta -> interdicted edge signal; alpha -> S/T set allocation --> theta is used to create the S/T set"""
        if m.artificial_edge[u, v]:
            # Infinite-capacity artificial edges cannot cross the cut.
            return m.alpha[u] <= m.alpha[v]
        return m.theta[u, v] >= m.alpha[u] - m.alpha[v]

    @staticmethod
    def st_boundary_rule(m:pyo.ConcreteModel) -> pyo.Constraint:
        """artificial source and sink but be in different parts of the cutset"""
        return m.alpha[m.s] - m.alpha[m.t] >= 1

    @staticmethod
    def interdiction_budget_rule(m: pyo.ConcreteModel) -> pyo.Constraint:
        """weighted cost must be less than the assigned bugdet"""
        return sum(m.interdiction_cost[n]*m.omega[n] for n in m.nodes) <= m.budget

    @staticmethod
    def artificial_node_interdiction_rule(m, n):
        """artificial nodes cannot be interdicted (they are conceptual devices used to control the graph)"""
        if m.artificial_node[n]:
            return m.omega[n] == 0
        return pyo.Constraint.Skip

    @staticmethod
    def cut_capacity_upper_rule(m, u, v):
        """linearization of node interdict multiplication constraints: part1"""
        if m.artificial_edge[u, v]:
            return pyo.Constraint.Skip
        return m.z[u, v] <= m.theta[u, v]

    @staticmethod
    def cut_capacity_node_u_rule(m, u, v):
        """linearization of node interdict multiplication constraints: part2"""
        if m.artificial_edge[u, v]:
            return pyo.Constraint.Skip
        return m.z[u, v] <= 1 - m.omega[u]

    @staticmethod
    def cut_capacity_node_v_rule(m, u, v):
        """linearization of node interdict multiplication constraints: part3"""
        if m.artificial_edge[u, v]:
            return pyo.Constraint.Skip
        return m.z[u, v] <= 1 - m.omega[v]

    @staticmethod
    def cut_capacity_lower_rule(m, u, v):
        """linearization of node interdict multiplication constraints: part4"""
        return m.z[u, v] >= m.theta[u, v]- m.omega[u] - m.omega[v]

