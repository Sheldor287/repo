Old_GRAPHMC_Class

class GraphMC:
    def __init__(self, solver:LP_Solver):
        self.solver = solver
        self.g = solver.g
        self.model = solver.model

    def _preprocess_network_simulation(self):
        self.nodes = list(self.g.nodes())
        self.edges = list(self.g.edges())
        self.node_p = np.array([self.g.nodes[n].get('probability1', 1) for n in self.nodes])
        self.edge_p = np.array([self.g.edges[n].get('probability', 1) for n in self.edges])

    def _process_result(self, result:dict, i:int) -> dict:
        flow = pyo.value(self.model.F)    
        node_operational = int(self.node_state.sum())
        node_failed = len(self.nodes) - node_operational
        edge_operational = int(self.edge_state.sum())
        edge_failed = len(self.edges) - edge_operational
        row = {
            'sim_number': i, 'flow': flow, 
            'node_operational': node_operational, 'node_failed': node_failed, 
            'edge_operational': edge_operational, 'edge_failed': edge_failed,
            'node_opr_ratio': node_operational/len(self.nodes), 
            'edge_opr_ratio': edge_operational/len(self.edges),
            'termination_condition': str(result.solver.termination_condition),
            'flow_failure_indicator': 1 if flow == 0 else 0
        }
        for n, state in zip(self.nodes, self.node_state):
            row[f'node_{n}'] = int(state)
        # Edge states
        for (u, v), state in zip(self.edges, self.edge_state):
            row[f'edge_({u},{v})'] = int(state)
        return row

    def _sample_states(self, rng) -> np.random:
        return rng.binomial(1, self.node_p), rng.binomial(1, self.edge_p)

    def stochastic_max_flow(self, n_sim:int=1000, seed:int=123, solver_str:str='appsi_highs') -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        pyo_solver = pyo.SolverFactory(solver_str)
        self._preprocess_network_simulation()
        results = []
        # simulation changes the lp-parameters, not the graph nor model
        for i in trange(n_sim):
            self.node_state, self.edge_state = self._sample_states(rng)
            for n, state in zip(self.nodes, self.node_state):
                self.model.node_state[n] = int(state)
            for (u, v), state in zip(self.edges, self.edge_state):
                self.model.edge_state[u, v] = int(state)
            result = pyo_solver.solve(self.model)
            results.append(self._process_result(result, i))
        return pd.DataFrame(results)
    
    @staticmethod
    def _get_influence_logic(df:pd.DataFrame, component_columns:list) -> pd.DataFrame:
        results = []
        for component in component_columns:
            flow_operational = df.loc[df[component] == 1, 'flow'].mean()
            flow_failed = df.loc[df[component] == 0, 'flow'].mean()
            results.append({
                'component': component,
                'flow_if_operational': flow_operational,
                'flow_if_failed': flow_failed if not None else 0,
                'flow_difference': flow_operational - flow_failed,
                'n_operational': (df[component] == 1).sum(),
                'n_failed': (df[component] == 0).sum() if not None else 0,
                'observed_performance_rate': (df[component] == 1).sum()/df.shape[0]
            })
        return pd.DataFrame(results).sort_values('flow_difference',ascending=False).reset_index(drop=True)

    def get_node_edge_influence(self, df:pd.DataFrame) -> pd.DataFrame:
        """ Function for getting additonal insights from stochastic max flow simulation """
        self.node_cols = [c for c in df.columns if re.match(r"\bnode_(\d+)\b", c)]
        self.edge_cols = [c for c in df.columns if re.match(r'^edge_\(\d+,\d+\)$',c)]
        node_df = self._get_influence_logic(df, self.node_cols).fillna(0)
        edge_df = self._get_influence_logic(df, self.edge_cols).fillna(0)
        return node_df, edge_df

    @staticmethod
    def plot_reliability_curve(df, flow_requirement=1):
        flow_values = np.sort(df['flow'])
        reliability = np.array([np.mean(df['flow'] >= f)for f in flow_values])
        plt.figure(figsize=(8, 5))
        plt.plot(flow_values, reliability, label=f'Probabilty G will have x independent paths')
        plt.axvline(flow_requirement,linestyle='--',label=f'Required flow: {flow_requirement}', c='red')
        plt.xlabel('Maximum Flow')
        plt.ylabel('Reliability')
        plt.title('Network Maximum-Flow Reliability Curve', weight='bold')
        plt.ylim(0, 1.02)
        plt.legend(loc='best')
        plt.grid(True, alpha=0.4)
        plt.show()

    def get_node_edge_importance(self, df) -> pd.DataFrame:
        """ 
        Returns:
        1. A dataframe of fit node/edge importances with respect to flow 
        2. A dataframe of permutation importances and anwsers the question:
                How much does shuffling results of a single node/arc effect the predicted outcome?
        """
        X = df[self.node_cols + self.edge_cols]
        y = df['flow']

        X_train, X_test, y_train, y_test = train_test_split(X, y,test_size=0.2,random_state=123)
        model = RandomForestRegressor(n_estimators=300,random_state=123,n_jobs=-1)
        model.fit(X_train, y_train)
        # using a permutation model instead --> stratifes successes and failures
        perm = permutation_importance(
            model,X_test,y_test,n_repeats=10,random_state=123,n_jobs=-1
        ) 

        #pred = model.predict(X_test)
        #print("R-squared:", r2_score(y_test, pred))
        #print("MAE:", mean_absolute_error(y_test, pred))

        importance_df = pd.DataFrame(
            {'component': X.columns,'importance': model.feature_importances_}
        ).sort_values('importance',ascending=False)
        perm_imp_df = pd.DataFrame(
            {'component': X.columns,'importance': perm.importances_mean}
        ).sort_values('importance',ascending=False)
        return importance_df, perm_imp_df