# optimization/visualization.py – Plot convergence curves (requires matplotlib)
import matplotlib.pyplot as plt
import numpy as np
from typing import List

def plot_convergence(history: List[float], title: str = "Convergence", save_path: str = None):
    plt.figure(figsize=(10,6))
    plt.plot(history)
    plt.xlabel("Iteration")
    plt.ylabel("Best Value")
    plt.title(title)
    plt.grid(True)
    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()
