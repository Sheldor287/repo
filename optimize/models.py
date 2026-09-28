from equations import Objectives, Rules
from toy_models.create import ToyGraph
from display import GraphDrawer
from analysis import Analysis
from pyomo import environ as pyo
import networkx as nx
import numpy as np

class LP:

    MODEL_CONFIGS = {
        'max_flow': {'model': 'primal', 'objective': 'max_flow',},
        'min_cut': {'model': 'min_cut', 'objective': 'min_cut',},
        'node_interdiction': {'model': 'interdiction','objective': 'min_cut','M':1, 'budget':9},
    }
    ALTERNATE_NAMES = {
    'max_flow': 'max_flow', 'mf': 'max_flow','standard_max_flow': 'max_flow','standard_mf': 'max_flow',
    'dual_maxflow': 'min_cut','min_cut': 'min_cut','min_cut_flow': 'min_cut',
    'zerosum_mf_static_nodes': 'node_interdiction', 'interdiction':'node_interdiction', 'node_interdiction': 'node_interdiction',
    'min_cost_flow': 'min_cost_flow','k_shortest_paths': 'k_shortest_paths',
    }

    def __init__(self,G:nx.DiGraph|ToyGraph ,model_type:str='max_flow',solver_str:str='appsi_highs',s:str='s',t:str='t',):
        self.g = G.G.copy() if hasattr(G, 'G') else G.copy()
        self.r = Rules()
        self.s = s
        self.t = t
        self.solver_str = solver_str
        try:
            self.model_type = self.ALTERNATE_NAMES[model_type]
        except KeyError:
            valid = ', '.join(self.ALTERNATE_NAMES)
            raise ValueError(f"Unknown model type '{model_type}\nValid types: {valid}")
        self.g = self.__configure_graph()
        self._create_problem_model()

    def _create_problem_model(self):
        config = self.MODEL_CONFIGS[self.model_type]
        if config['model'] == 'primal':
            self.model = self._create_primal_model()
        elif config['model'] == 'min_cut':
            self.model = self._create_min_cut_model()
        elif config['model'] == 'interdiction':
            self.model = self._create_node_interdiction_model(budget=config['budget'],M=config['M'],)
        else:
            raise ValueError(f"Unknown model class: {config['model']}")

    def _create_base_model(self) -> pyo.ConcreteModel:
        model = pyo.ConcreteModel()
        model.nodes = pyo.Set(initialize=list(self.g.nodes()))
        model.edges = pyo.Set(initialize=list(self.g.edges()), dimen=2)
        # used for monte-carlo simulation
        model.node_state = pyo.Param(model.nodes, within=pyo.Binary, mutable=True, initialize=1)
        model.edge_state = pyo.Param(model.edges, within=pyo.Binary, mutable=True, initialize=1)
        model.capacity = pyo.Param(model.edges,initialize={(u, v): self.g.edges[u, v]['capacity'] for u, v in self.g.edges()})
        model.cost = pyo.Param(model.edges, initialize={(u,v): self.g.edges[u,v]['cost'] for u,v in self.g.edges()})
        model.artificial_edge = pyo.Param(
            model.edges, within=pyo.Binary, 
            initialize={(u,v): int(self.g.edges[u,v].get('artificial', False)) for u,v in self.g.edges()}
            )
        model.artificial_node = pyo.Param(
            model.nodes, within=pyo.Binary, 
            initialize={n: int(self.g.nodes[n].get('artificial', False)) for n in self.g.nodes()}
            )
        model.s = self.s
        model.t = self.t
        return model
    
    def _create_primal_model(self) -> pyo.ConcreteModel:
        "Standard maxflow problem"
        model = self._create_base_model()
        # Decisions
        model.x = pyo.Var(model.edges, within=pyo.NonNegativeReals)
        model.F = pyo.Var(within=pyo.NonNegativeReals)
        # Params
        model.demand = pyo.Param(model.nodes,initialize={n: self.g.nodes[n]['demand'] for n in self.g.nodes()})
        # Constraints
        model.cap = pyo.Constraint(model.edges, rule=self.r.edge_cap_rule)
        model.flow = pyo.Constraint(model.nodes, rule=self.r.edge_flow_rule)
        model.source = pyo.Constraint(rule=self.r.source_flow_rule)
        model.sink = pyo.Constraint(rule=self.r.sink_flow_rule)
        model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
        Objectives.apply('max_flow', model)
        return model

    def _create_min_cut_model(self) -> pyo.ConcreteModel:
        "Standard mincut problem (dual of maxflow)"
        model = self._create_base_model()
        model.theta = pyo.Var(model.edges, within=pyo.NonNegativeReals) # ST-cut indicator variable
        model.alpha = pyo.Var(model.nodes, within=pyo.UnitInterval) # ST-cut forcing variable -- range: [0,1]
        model.cutset = pyo.Constraint(model.edges,rule=self.r.cutset_rule)
        model.stflow = pyo.Constraint(rule=self.r.st_boundary_rule)
        Objectives.apply('min_cut', model)
        return model

    def _create_node_interdiction_model(self,budget:float=9,M:int=1,) -> pyo.ConcreteModel:
        model = self._create_base_model()
        # P1 maxflow variables
        model.theta = pyo.Var(model.edges,within=pyo.NonNegativeReals)
        model.alpha = pyo.Var(model.nodes,within=pyo.UnitInterval)
        # P2 interdiction variables
        model.omega = pyo.Var(model.nodes,within=pyo.Binary)
        model.w = pyo.Var(model.edges,within=pyo.Binary)
        # Aux params
        model.M = pyo.Param(initialize=M,within=pyo.PositiveReals)
        model.interdiction_cost = pyo.Param(model.nodes,initialize={n: self.g.nodes[n].get('cost', 0) for n in model.nodes})
        model.budget = pyo.Param(initialize=budget,within=pyo.NonNegativeReals)
        # Constraints
        model.cutset = pyo.Constraint(model.edges,rule=self.r.cutset_rule)
        model.stflow = pyo.Constraint(rule=self.r.st_boundary_rule)
        model.budget_limit = pyo.Constraint(rule=self.r.interdiction_budget_rule)
        model.artificial_protection = pyo.Constraint(model.nodes,rule=self.r.artificial_node_interdiction_rule)
        # W linearization
        model.w1 = pyo.Constraint(model.edges, rule=self.r.cut_capacity_upper_rule)
        model.w2 = pyo.Constraint(model.edges, rule=self.r.cut_capacity_lower_rule)
        model.w3 = pyo.Constraint(model.edges, rule=self.r.cut_capacity_node_u_rule)
        model.w4 = pyo.Constraint(model.edges, rule=self.r.cut_capacity_node_v_rule)
        Objectives.apply('interdicted_min_cut_flow',model)
        return model

    def solve(self):
        return Solver(self)

    def _solve_model(self):
        solver = pyo.SolverFactory(self.solver_str)
        return solver.solve(self.model)

    def __configure_graph(self, source='s', sink='t', artificial_source='dS', artificial_sink='dT'):
        """
        Standardizes the graph for LPs including:
        1. Creating super-source/sink artificial nodes
        2. Standardizing cost/capacity parameters for edges
        3. Standardizing demand parameter for nodes 
        4. Create an artificial source/sink to preserve demand balance 
        """
        H = self.g.copy()
        if not H.is_directed():
            H = H.to_directed()
        for _,_,d in H.edges(data=True):
            d.setdefault('capacity', 1)
            d.setdefault('cost', 0)
        for n, data in H.nodes(data=True):
            data.setdefault('demand', 0)
        finite_capacities = [d["capacity"] for _, _, d in H.edges(data=True) if np.isfinite(d["capacity"])]
        artificial_capacity = sum(finite_capacities)
        # Add super source/sink
        H.add_node(source, demand=0, layer=-1, artificial=True)
        H.add_node(sink, demand=0, layer=1+max(d['layer'] for _,d in H.nodes(data=True)), artificial=True)
        supply = [n for n in H.nodes if H.nodes[n].get('demand') < 0]
        demand = [n for n in H.nodes if H.nodes[n].get('demand') > 0]
        for n in supply:
            H.add_edge(source, n, capacity=artificial_capacity, cost=0, artificial=True)
        for n in demand:
            H.add_edge(n, sink, capacity=artificial_capacity, cost=0, artificial=True)
        # Normalize demand balance
        demand_imbalance = sum(-H.nodes[n]['demand'] for n in supply) - sum(H.nodes[n]['demand'] for n in demand)
        if demand_imbalance > 0:
            H.add_node(artificial_sink, demand=0, artificial=True, layer=-1)
            H.add_edge(source, artificial_sink, capacity=demand_imbalance, cost=0, artificial=True)
            H.add_edge(artificial_sink, sink, capacity=demand_imbalance, cost=0, artificial=True)
        elif demand_imbalance < 0:
            H.add_node(artificial_source, demand=0, artificial=True, layer=1+max(d['layer'] for _,d in H.nodes(data=True)))
            H.add_edge(artificial_source, sink, capacity=-demand_imbalance, cost=0, artificial=True)
            H.add_edge(source, artificial_source, capacity=-demand_imbalance, cost=0, artificial=True)
        return H
    
    def fix_interdiction(self, interdictions):
        """
        Fix omega based on an iterable of nodes to interdict.
        Only valid for node-interdiction models.
        """
        if self.model_type != 'node_interdiction':
            raise ValueError("Interdiction decisions only exist for node_interdiction models.")
        interdictions = set(interdictions)
        for n in self.model.nodes:
            self.model.omega[n].fix(1 if n in interdictions else 0)

class Solver:
    RESULT_BUILDERS = {
        'max_flow': '_build_max_flow_results',
        'min_cut': '_build_min_cut_results',
        'node_interdiction': '_build_node_interdiction_results',
    }

    def __init__(self, lp: LP):
        self.lp = lp
        self.g = lp.g
        self.model = lp.model
        self.model_type = lp.model_type

        self.solver_result = lp._solve_model()
        self.results = self._build_results()

    # Complete Functions
    def get_node_results(self):
        return self.results['node_results']

    def get_edge_results(self):
        return self.results['edge_results']

    def get_metrics(self):
        return self.results['metrics']

    def analyze(self):
        return Analysis(self)

    def draw(self):
        return GraphDrawer(self)

    # Result allocator from model type
    def _build_results(self):
        try:
            builder_name = self.RESULT_BUILDERS[self.model_type]
        except KeyError:
            raise NotImplementedError(f"No result generator for model type: {self.model_type}")
        return getattr(self, builder_name)()

    # Common results
    def _base_results(self):
        return {'problem': self._get_problem_results(),'solver': self._get_solver_results(),}
    
    def _get_problem_results(self):
        result = self.solver_result
        return {
            'lower_bound': result['Problem']()['Lower bound'],'upper_bound': result['Problem']()['Upper bound'],
            'objective_value': pyo.value(self.model.obj), 'obj_function_count': self.model.nobjectives(),
            'constraint_count': self.model.nconstraints(),'variable_count': self.model.nvariables(),'sense': str(self.model.obj.sense),
        }

    def _get_solver_results(self):
        result = self.solver_result
        return {
            'status': str(result['Solver']()['Status']),
            'termination_condition': str(result['Solver']()['Termination condition']),
            'termination_message': str(result['Solver']()['Termination message']),
        }

    # Result builders
    def _build_max_flow_results(self):
        results = self._base_results()
        node_results = self._get_primal_node_results()
        edge_results = self._get_primal_edge_results()
        # Statistics
        supply_nodes = [r for r in node_results.values() if r['node_type'] == 'supply']
        demand_nodes = [r for r in node_results.values() if r['node_type'] == 'demand']
        total_supply = sum(-r['demand'] for r in supply_nodes)
        total_used_supply = sum(r['demand_satisfied'] for r in supply_nodes)
        total_demand = sum(r['demand'] for r in demand_nodes)
        total_satisfied = sum(r['demand_satisfied']for r in demand_nodes)
        total_unmet = total_demand - total_satisfied
        # Record Results
        results['node_results'] = node_results
        results['edge_results'] = edge_results
        results['metrics'] = {
            'total_supply': total_supply,
            'total_used_supply': total_used_supply,
            'total_unused_supply': (total_supply - total_used_supply),
            'total_demand': total_demand,
            'total_satisfied': total_satisfied,
            'total_unmet': total_unmet,
            'bottlenecks': self._get_bottlenecks(),
            'total_satisfaction_rate': (total_satisfied / total_demand if total_demand > 0 else None),
        }
        return results

    def _build_min_cut_results(self):
        results = self._base_results()
        node_results = self._get_dual_node_results()
        edge_results = self._get_dual_edge_results()
        metrics = self._get_dual_metrics(edge_results)
        results["node_results"] = node_results
        results["edge_results"] = edge_results
        results["metrics"] = metrics
        return results
    
    def _build_node_interdiction_results(self):
        results = self._base_results()

        node_results = self._get_interdiction_node_results()
        edge_results = self._get_interdiction_edge_results()
        metrics = self._get_interdiction_metrics(edge_results)

        results["node_results"] = node_results
        results["edge_results"] = edge_results
        results["metrics"] = metrics

        return results
    
    # Edge results
    def _get_primal_edge_results(self):
        edge_results = {}
        for u, v in self.model.edges:
            flow = pyo.value(self.model.x[u, v])
            capacity = pyo.value(self.model.capacity[u, v])
            cost = pyo.value(self.model.cost[u, v])
            edge_results[(u, v)] = {
                'flow': flow, 
                'capacity': capacity, 
                'residual': capacity - flow,
                'utilization': (flow / capacity if capacity > 0 and capacity != float('inf') else 0),
                'cost': cost,
                'total_cost': flow * cost,
                'artificial': self.g.edges[u, v].get('artificial', False)
            }
        return edge_results

    def _get_dual_edge_results(self):
        """Collect edge-level results for the standard min-cut model."""
        edge_results = {}
        for u, v in self.model.edges:
            artificial = bool(pyo.value(self.model.artificial_edge[u, v]))
            # Artificial edges are visualization-only.
            # Their theta variables are intentionally irrelevant
            if artificial:
                edge_results[(u, v)] = {
                    "theta": None,
                    "in_cut": False,
                    "capacity": pyo.value(self.model.capacity[u, v]),
                    "cut_capacity": 0.0,
                    "artificial": True,
                }
                continue
            theta = pyo.value(self.model.theta[u, v])
            capacity = pyo.value(self.model.capacity[u, v])
            edge_results[(u, v)] = {
                "theta": theta,
                "in_cut": theta > 0.5,
                "capacity": capacity,
                "cut_capacity": theta * capacity,
                "artificial": False,
            }
        return edge_results

    def _get_interdiction_edge_results(self):
        """Collect edge-level results for the node-interdiction min-cut model."""
        edge_results = {}
        for u, v in self.model.edges:
            theta = pyo.value(self.model.theta[u, v])
            z = pyo.value(self.model.w[u, v])
            capacity = pyo.value(self.model.capacity[u, v])
            omega_u = pyo.value(self.model.omega[u])
            omega_v = pyo.value(self.model.omega[v])
            artificial = bool(pyo.value(self.model.artificial_edge[u, v]))
            endpoint_interdicted = (omega_u > 0.5 or omega_v > 0.5)
            in_cut = theta > 0.5
            in_interdicted_cut = z > 0.5
            edge_results[(u, v)] = {
                "theta": theta,         # Cut variables
                "in_cut": in_cut,
                "z": z,                 # Interdiction
                "in_interdicted_cut": in_interdicted_cut,
                "omega_u": omega_u,     # Endpoint Interdiction
                "omega_v": omega_v,
                "endpoint_interdicted": endpoint_interdicted,
                "capacity": capacity,   # Capacity
                "cut_capacity": capacity * theta,
                "interdicted_cut_capacity": capacity * z,
                "capacity_removed": capacity * (theta - z), # Impact classification
                "artificial": artificial,
            }
        return edge_results

    # Node results
    def _get_primal_node_results(self):
        node_results = {}
        for n, d in self.g.nodes(data=True):
            demand = d.get('demand', 0)
            node_type = 'supply' if demand < 0 else 'demand' if demand > 0 else 'transshipment'
            inflow = sum(pyo.value(self.model.x[u, n]) for u in self.g.nodes if (u,n) in self.model.edges)
            outflow = sum(pyo.value(self.model.x[n,v]) for v in self.g.nodes if (n,v) in self.model.edges)
            if (self.model.s, n) in self.model.edges:
                satisfied = pyo.value(self.model.x[self.model.s, n]) 
            elif (n, self.model.t) in self.model.edges:
                satisfied = pyo.value(self.model.x[n, self.model.t])
            else:
                satisfied = 0
            node_results[n] = {
                'node_type': node_type,
                'inflow': inflow,
                'outflow': outflow,
                'demand': demand,
                'remaining_supply': -(demand + inflow - outflow) if node_type == 'supply' else 0,
                'demand_satisfied': satisfied,
                'satisfaction_rate': abs(satisfied/demand) if demand != 0 else 0, 
                'cutset_group': self._get_dual(self.model.flow[n]) if n not in ('s', 't') else None 
            }
        return node_results 

    def _get_dual_node_results(self):
        """Collect node-level results for the standard min-cut model."""
        node_results = {}
        for n in self.model.nodes:
            alpha = pyo.value(self.model.alpha[n])
            artificial = bool(pyo.value(self.model.artificial_node[n]))
            node_results[n] = {
                "alpha": alpha,"source_side": alpha < 0.5,"sink_side": alpha >= 0.5,"artificial": artificial,
            }
        return node_results

    def _get_interdiction_node_results(self):
        """Collect node-level results for the node-interdiction model."""
        node_results = {}
        for n in self.model.nodes:
            omega = pyo.value(self.model.omega[n])
            alpha = pyo.value(self.model.alpha[n])
            interdiction_cost = pyo.value(self.model.interdiction_cost[n])
            artificial = bool(pyo.value(self.model.artificial_node[n]))
            node_results[n] = {
                # Interdiction
                "omega": omega,
                "interdicted": omega > 0.5,
                "interdiction_cost": interdiction_cost,
                # Cut partition
                "alpha": alpha,
                "source_side": alpha < 0.5,
                "sink_side": alpha >= 0.5,
                # Graph metadata
                "artificial": artificial,
            }
        return node_results

    def _get_dual_metrics(self, edge_results):
        """Calculate aggregate metrics for the standard min-cut."""
        cut_edges = [edge for edge, data in edge_results.items() if data["in_cut"]]
        cut_capacity = sum(edge_results[edge]["cut_capacity"] for edge in cut_edges if not edge_results[edge]["artificial"])
        return {"cut_capacity": cut_capacity, "cut_edges": cut_edges, "cut_size": len(cut_edges),}

    def _get_interdiction_metrics(self, edge_results):
        """Calculate aggregate metrics for the node-interdiction solution."""
        real_edges = { edge: data for edge, data in edge_results.items() if not data["artificial"] }
        cut_edges = [ edge for edge, data in real_edges.items() if data["in_cut"] ]
        interdicted_cut_edges = [ edge for edge, data in real_edges.items() if data["in_interdicted_cut"] ]
        interdicted_edges = [ edge for edge, data in real_edges.items() if data["endpoint_interdicted"] ]
        cut_capacity = sum( data["cut_capacity"] for data in real_edges.values() )
        interdicted_cut_capacity = sum( data["interdicted_cut_capacity"] for data in real_edges.values() )
        capacity_removed = sum( data["capacity_removed"] for data in real_edges.values() )
        interdicted_nodes = [ n for n in self.model.nodes if pyo.value(self.model.omega[n]) > 0.5 and not pyo.value(self.model.artificial_node[n]) ]
        interdiction_cost = sum( 
            pyo.value(self.model.interdiction_cost[n]) * pyo.value(self.model.omega[n]) for n in self.model.nodes if not pyo.value(self.model.artificial_node[n]) 
        )
        budget = pyo.value(self.model.budget)
        return {
            "cut_capacity": cut_capacity,
            "interdicted_cut_capacity": interdicted_cut_capacity,
            "capacity_removed": capacity_removed,
            # Edge metrics
            "cut_edges": cut_edges,
            "interdicted_cut_edges": interdicted_cut_edges,
            "interdicted_edges": interdicted_edges,
            "cut_size": len(cut_edges),
            "interdicted_cut_size": len(interdicted_cut_edges),
            # Node interdiction 
            "interdicted_nodes": interdicted_nodes,
            "interdiction_count": len(interdicted_nodes),
            "interdiction_cost": interdiction_cost,
            "budget": budget,
        }

    # Graph results
    def draw_modified_graph(self):
        pos = nx.art_layout(self.g)
        nx.draw(self.g, pos=pos, with_labels=True, node_color='lightblue', 
                node_size=self.node_size, font_size=16, font_weight='bold', arrowsize=20
        )

    def get_residual_graph(self):
        if not hasattr(self.model, 'x'):
            raise AttributeError(f"Model '{self.model_type}' does not have primal flow variable 'x'")
        R = nx.DiGraph()
        for u,v in self.model.edges:
            capacity = pyo.value(self.model.capacity[u,v])
            flow = pyo.value(self.model.x[u,v])
            forward = capacity - flow
            reverse = flow
            if forward > 0:
                R.add_edge(u,v,residual=forward)
            if reverse > 0:
                R.add_edge(v,u, residual=reverse)
        return R  

    # Aux Statistics
    def _get_bottlenecks(self):
        if not hasattr(self.model, 'dual'):
            return None
        bottlenecks = []
        for edge in self.model.edges:
            constraint = self.model.cap[edge]
            dual = self.model.dual.get(constraint)
            if dual is not None and dual > 0:
                bottlenecks.append(edge)
        return bottlenecks

    def _get_dual(self, constraint:pyo.Constraint) -> pyo.Constraint:
        return None if not hasattr(self.model, 'dual') else self.model.dual.get(constraint)


