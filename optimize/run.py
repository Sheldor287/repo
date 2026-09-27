from toy_models.create import ToyGraph
from models import LP
if __name__ == "__main__":
    toy = ToyGraph()
    solution = LP(toy,model_type='zerosum_mf_static_nodes').solve()
    drawer = solution.draw()
    analysis = solution.analyze()
    ml = analysis.ml()

""" 
Workflow options include:

model_type in ['max_flow','min_cost_flow','min_cut','interdicted_min_cut_flow']
df --> analysis.stochastic_analysis(n_sim=50,seed=123,)


# Inspection based on problem type
analysis.summary()
analysis.get_node_results()
analysis.get_edge_results()
analysis.get_metrics()

if model_type == 'min_cut':
    analysis.get_cut_edges()
    cut_frequency = analysis.cut_frequency(df)
    cut_persistence = analysis.cut_persistence(df)
    cut_diversity = analysis.cut_diversity(df)
    bottlenecks = analysis.bottleneck_analysis(df)

if model_type == 'interdiction':
    analysis.get_interdicted_nodes()
    analysis.get_interdicted_cut_edges()
    analysis.get_interdiction_cost()
    analysis.get_interdiction_efficiency()
    attack_surface = analysis.attack_surface(df)
    efficiency = analysis.interdiction_efficiency(df)
    natural_vs_adversarial = analysis.natural_failure_vs_adversarial_failure(df)
    capacity_loss = analysis.capacity_loss(df)

# Stochastic dataframe & analysis
df = analysis.stochastic_analysis(n_sim=50,seed=123,)
analysis.performance_summary(df, y_column="objective",)
analysis.reliability(df,threshold=10,)
analysis.failure_probability(df,threshold=10,)
analysis.plot_reliability_curve(df,threshold=10,)
node_influence, edge_influence = analysis.get_component_influence(df,y_column="objective",)
reliability = analysis.get_component_reliability(df,threshold=10,)
"""