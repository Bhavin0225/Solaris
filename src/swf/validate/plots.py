"""Validation scatter plots. matplotlib is imported lazily so serving/core stay matplotlib-free."""

from pathlib import Path


def scatter(sim, act, path: Path, title: str, cap_kw: float, units: str = "kW") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 5))
    if len(sim) > 20_000:
        ax.hexbin(act, sim, gridsize=60, mincnt=1, extent=(0, 1.05 * cap_kw, 0, 1.05 * cap_kw), bins="log")
    else:
        ax.scatter(act, sim, s=4, alpha=0.3)
    ax.plot([0, cap_kw], [0, cap_kw], "k--", lw=1)
    ax.set_xlim(0, 1.05 * cap_kw)
    ax.set_ylim(0, 1.05 * cap_kw)
    ax.set_xlabel(f"Actual ({units})")
    ax.set_ylabel(f"Simulated ({units})")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120, metadata={"Software": None})
    plt.close(fig)
