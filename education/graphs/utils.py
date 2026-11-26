from __future__ import annotations
import numpy as np
import networkx as nx
from matplotlib import pyplot as plt
import matplotlib.patches as mpatches

PLOT_KW = {"node_size": 600, "node_color": "skyblue", "font_weight": "bold", "with_labels": True}
PLOT_C = {"node_size": 600, "font_weight": "bold", "with_labels": True}

def random_radial(r=1, n=10, func=np.random.uniform, seed=123):
    np.random.seed(seed)
    TAU = 2*np.pi
    theta = np.linspace(0, TAU, n) + np.random.normal(0, TAU/np.sqrt(n), size=n)
    radius = func(0, r, size=n)
    return radius*np.cos(theta), radius*np.sin(theta)

def seperation_example():
    edges = [(0,1),(0,2),(1,2),(2,3),(3,4),(3,5),(4,5)]
    pos = {0:(0,2),1:(0,0),2:(1,1),3:(2,1),4:(3,2),5:(3,0),}
    G = nx.Graph()
    G.add_edges_from(edges)

    fig, _ = plt.subplots(figsize=(12, 4))
    nx.draw(G, pos, **PLOT_C, node_color=np.repeat(['tomato', 'skyblue', 'lime'], 2))
    text=[('tomato', 'Set A'), ('lime', 'Set B'), ('skyblue', 'Set S'), ]
    handles = [mpatches.Patch(color=c, label=s) for (c,s) in text]
    plt.legend(handles=handles, loc='lower center')
    plt.show()
    return fig
