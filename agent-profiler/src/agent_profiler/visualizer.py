"""Visualization tools for agent profiling results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_profiler.profiler import ProfileResult, AgentProfiler


class ProfileVisualizer:
    """Generate charts and visualizations for agent profiles."""

    def __init__(self, style: str = "default") -> None:
        self.style = style
        self._setup_matplotlib()

    def _setup_matplotlib(self) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            plt.style.use(self.style if self.style != "default" else "seaborn-v0_8-whitegrid")
        except (ImportError, OSError):
            pass

    def generate_profile_chart(self, profile: ProfileResult, output: str | Path | None = None) -> Any:
        """Generate a radar chart showing profile scores.

        Args:
            profile: ProfileResult from AgentProfiler.
            output: Path to save the chart. If None, displays interactively.

        Returns:
            matplotlib Figure object.
        """
        import matplotlib.pyplot as plt
        import numpy as np

        categories = list(profile.profile_scores.keys())
        values = [profile.profile_scores.get(c, 0.0) for c in categories]

        N = len(categories)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        values_closed = values + [values[0]]
        angles_closed = angles + [angles[0]]

        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

        ax.fill(angles_closed, values_closed, alpha=0.25, color="steelblue")
        ax.plot(angles_closed, values_closed, linewidth=2, color="steelblue")

        ax.set_xticks(angles)
        ax.set_xticklabels([c.title() for c in categories], fontsize=11)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])

        ax.set_title(
            f"Agent Profile: {profile.category.title()}\n"
            f"Confidence: {profile.confidence:.1%} | Turns: {profile.num_turns} | "
            f"Duration: {profile.session_duration:.0f}s",
            fontsize=13,
            fontweight="bold",
            pad=20,
        )

        highlight_idx = categories.index(profile.category) if profile.category in categories else 0
        ax.plot(
            [angles[highlight_idx], angles[highlight_idx]],
            [0, values[highlight_idx]],
            linewidth=3,
            color="coral",
            linestyle="--",
        )
        ax.scatter(
            [angles[highlight_idx]],
            [values[highlight_idx]],
            color="coral",
            s=100,
            zorder=5,
        )

        fig.tight_layout()

        if output:
            fig.savefig(str(output), dpi=150, bbox_inches="tight")
            plt.close(fig)

        return fig

    def generate_transition_heatmap(self, session: str | Path | list[dict[str, Any]], output: str | Path | None = None) -> Any:
        """Generate a heatmap of tool transition probabilities.

        Args:
            session: JSONL trace file or list of trace dicts.
            output: Path to save the chart.

        Returns:
            matplotlib Figure object.
        """
        import matplotlib.pyplot as plt
        import numpy as np

        profiler = AgentProfiler()
        if isinstance(session, (str, Path)):
            result = profiler.profile(session)
        else:
            result = profiler.profile(session)

        transitions = result.transition_analysis
        tools = sorted(set(list(transitions.transitions.keys()) +
                          [t for tos in transitions.transitions.values() for t in tos.keys()]))

        if not tools:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, "No transitions found", ha="center", va="center", fontsize=14)
            ax.set_title("Tool Transition Heatmap", fontsize=13, fontweight="bold")
            fig.tight_layout()
            if output:
                fig.savefig(str(output), dpi=150, bbox_inches="tight")
                plt.close(fig)
            return fig

        n = len(tools)
        matrix = np.zeros((n, n))
        probs = transitions.transition_probabilities

        for i, from_tool in enumerate(tools):
            for j, to_tool in enumerate(tools):
                matrix[i][j] = probs.get(from_tool, {}).get(to_tool, 0.0)

        fig, ax = plt.subplots(figsize=(max(8, n + 2), max(6, n)))
        im = ax.imshow(matrix, cmap="YlOrRd", vmin=0, vmax=1.0)

        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(tools, rotation=45, ha="right", fontsize=10)
        ax.set_yticklabels(tools, fontsize=10)

        for i in range(n):
            for j in range(n):
                if matrix[i][j] > 0.01:
                    ax.text(j, i, f"{matrix[i][j]:.2f}", ha="center", va="center",
                            fontsize=8, color="white" if matrix[i][j] > 0.5 else "black")

        ax.set_title("Tool Transition Probabilities", fontsize=13, fontweight="bold", pad=10)
        ax.set_xlabel("To Tool", fontsize=11)
        ax.set_ylabel("From Tool", fontsize=11)

        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("Transition Probability", fontsize=10)

        fig.tight_layout()

        if output:
            fig.savefig(str(output), dpi=150, bbox_inches="tight")
            plt.close(fig)

        return fig

    def generate_tool_distribution_pie(self, session: str | Path | list[dict[str, Any]], output: str | Path | None = None) -> Any:
        """Generate a pie chart of tool usage distribution.

        Args:
            session: JSONL trace file or list of trace dicts.
            output: Path to save the chart.

        Returns:
            matplotlib Figure object.
        """
        import matplotlib.pyplot as plt

        profiler = AgentProfiler()
        if isinstance(session, (str, Path)):
            result = profiler.profile(session)
        else:
            result = profiler.profile(session)

        dist = result.tool_distribution

        if not dist.tool_counts:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, "No tool usage data", ha="center", va="center", fontsize=14)
            ax.set_title("Tool Distribution", fontsize=13, fontweight="bold")
            fig.tight_layout()
            if output:
                fig.savefig(str(output), dpi=150, bbox_inches="tight")
                plt.close(fig)
            return fig

        tools = list(dist.tool_counts.keys())
        counts = list(dist.tool_counts.values())

        colors = {
            "read": "#4e79a7", "edit": "#f28e2b", "write": "#e15759",
            "bash": "#59a14f", "grep": "#76b7b2", "unknown": "#b07aa1",
        }
        pie_colors = [colors.get(t, "#bab0ac") for t in tools]

        fig, ax = plt.subplots(figsize=(8, 6))
        wedges, texts, autotexts = ax.pie(
            counts, labels=[t.title() for t in tools], autopct="%1.1f%%",
            colors=pie_colors, startangle=90, pctdistance=0.8,
        )
        for t in texts:
            t.set_fontsize(10)
        for t in autotexts:
            t.set_fontsize(9)

        ax.set_title(
            f"Tool Distribution ({dist.total_calls} calls)\n"
            f"Dominant: {dist.dominant_tool.title()} | Entropy: {dist.entropy:.2f}",
            fontsize=13,
            fontweight="bold",
        )

        fig.tight_layout()

        if output:
            fig.savefig(str(output), dpi=150, bbox_inches="tight")
            plt.close(fig)

        return fig
