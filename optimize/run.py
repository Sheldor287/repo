from toy_models.create import ToyGraph
from models import LP
if __name__ == "__main__":
    toy = ToyGraph()
    solution = LP(toy,model_type='zerosum_mf_static_nodes').solve()
    drawer = solution.draw()
    analysis = solution.analyze()
    ml = analysis.ml()
