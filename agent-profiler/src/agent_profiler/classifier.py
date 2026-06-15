"""Behavior classification using pretrained profiles and transition matrices."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BehaviorProfile:
    """A predefined behavior profile template."""

    name: str
    description: str
    edit_weight: float = 0.0
    read_weight: float = 0.0
    grep_weight: float = 0.0
    bash_weight: float = 0.0
    write_weight: float = 0.0
    error_rate_weight: float = 0.0
    error_recovery_weight: float = 0.0
    circular_weight: float = 0.0
    entropy_weight: float = 0.0
    min_turns: int = 0


class DebuggingProfile(BehaviorProfile):
    """Profile for debugging sessions: high edit+bash, many errors, recoveries."""

    def __init__(self) -> None:
        super().__init__(
            name="debugging",
            description="Active debugging with edits and error recovery loops",
            edit_weight=0.25,
            read_weight=0.15,
            grep_weight=0.10,
            bash_weight=0.30,
            write_weight=0.05,
            error_rate_weight=0.40,
            error_recovery_weight=0.35,
            circular_weight=0.20,
            entropy_weight=0.15,
            min_turns=5,
        )


class BuildingProfile(BehaviorProfile):
    """Profile for productive building: high write+bash, low read."""

    def __init__(self) -> None:
        super().__init__(
            name="building",
            description="Active feature development with writes and executions",
            edit_weight=0.15,
            read_weight=0.10,
            grep_weight=0.05,
            bash_weight=0.25,
            write_weight=0.30,
            error_rate_weight=-0.10,
            error_recovery_weight=0.10,
            circular_weight=0.05,
            entropy_weight=0.20,
            min_turns=3,
        )


class ExploringProfile(BehaviorProfile):
    """Profile for exploration: high read+grep, low edit."""

    def __init__(self) -> None:
        super().__init__(
            name="exploring",
            description="Code exploration with reads and searches, minimal edits",
            edit_weight=0.05,
            read_weight=0.35,
            grep_weight=0.30,
            bash_weight=0.10,
            write_weight=0.02,
            error_rate_weight=-0.20,
            error_recovery_weight=0.05,
            circular_weight=0.10,
            entropy_weight=0.25,
            min_turns=3,
        )


class LostProfile(BehaviorProfile):
    """Profile for lost/confused sessions: circular transitions, high read."""

    def __init__(self) -> None:
        super().__init__(
            name="lost",
            description="Confused or circular behavior, reading without progress",
            edit_weight=0.05,
            read_weight=0.35,
            grep_weight=0.15,
            bash_weight=0.05,
            write_weight=0.02,
            error_rate_weight=0.10,
            error_recovery_weight=-0.10,
            circular_weight=0.40,
            entropy_weight=0.10,
            min_turns=5,
        )


class VerifyingProfile(BehaviorProfile):
    """Profile for verification: read after edit, test runs."""

    def __init__(self) -> None:
        super().__init__(
            name="verifying",
            description="Verifying changes with reads after edits and test execution",
            edit_weight=0.20,
            read_weight=0.30,
            grep_weight=0.10,
            bash_weight=0.25,
            write_weight=0.05,
            error_rate_weight=-0.05,
            error_recovery_weight=0.25,
            circular_weight=0.15,
            entropy_weight=0.15,
            min_turns=4,
        )


class BehaviorClassifier:
    """Classify agent behavior using pretrained profiles and scoring."""

    def __init__(self) -> None:
        self.profiles: dict[str, BehaviorProfile] = {
            "debugging": DebuggingProfile(),
            "building": BuildingProfile(),
            "exploring": ExploringProfile(),
            "lost": LostProfile(),
            "verifying": VerifyingProfile(),
        }

    def compute_scores(
        self,
        edit_ratio: float = 0.0,
        read_ratio: float = 0.0,
        grep_ratio: float = 0.0,
        bash_ratio: float = 0.0,
        write_ratio: float = 0.0,
        error_rate: float = 0.0,
        error_recovery_rate: float = 0.0,
        circular_ratio: float = 0.0,
        entropy: float = 0.0,
        num_turns: int = 0,
    ) -> dict[str, float]:
        """Compute profile scores for each behavior category.

        Args:
            edit_ratio: Ratio of edit tool calls.
            read_ratio: Ratio of read tool calls.
            grep_ratio: Ratio of grep/search tool calls.
            bash_ratio: Ratio of bash/shell tool calls.
            write_ratio: Ratio of write tool calls.
            error_rate: Rate of errors in the session.
            error_recovery_rate: Rate of error recovery.
            circular_ratio: Ratio of circular tool transitions.
            entropy: Entropy of tool distribution.
            num_turns: Number of turns in the session.

        Returns:
            Dict mapping category name to confidence score (0-1).
        """
        scores: dict[str, float] = {}

        features = {
            "edit": edit_ratio,
            "read": read_ratio,
            "grep": grep_ratio,
            "bash": bash_ratio,
            "write": write_ratio,
            "error_rate": error_rate,
            "error_recovery": error_recovery_rate,
            "circular": circular_ratio,
            "entropy": entropy,
        }

        for name, profile in self.profiles.items():
            profile_features = {
                "edit": profile.edit_weight,
                "read": profile.read_weight,
                "grep": profile.grep_weight,
                "bash": profile.bash_weight,
                "write": profile.write_weight,
                "error_rate": profile.error_rate_weight,
                "error_recovery": profile.error_recovery_weight,
                "circular": profile.circular_weight,
                "entropy": profile.entropy_weight,
            }

            dot_product = sum(
                features.get(k, 0.0) * profile_features.get(k, 0.0)
                for k in set(list(features.keys()) + list(profile_features.keys()))
            )

            obs_vec = np.array([features.get(k, 0.0) for k in sorted(features.keys())])
            prof_vec = np.array([profile_features.get(k, 0.0) for k in sorted(features.keys())])

            obs_norm = np.linalg.norm(obs_vec)
            prof_norm = np.linalg.norm(prof_vec)

            if obs_norm > 0 and prof_norm > 0:
                cosine_sim = float(np.dot(obs_vec, prof_vec) / (obs_norm * prof_norm))
            else:
                cosine_sim = 0.0

            score = (dot_product + (cosine_sim + 1) / 2) / 2.0

            if num_turns < profile.min_turns:
                score *= 0.5

            scores[name] = max(0.0, min(1.0, score))

        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    def classify(
        self,
        edit_ratio: float = 0.0,
        read_ratio: float = 0.0,
        grep_ratio: float = 0.0,
        bash_ratio: float = 0.0,
        write_ratio: float = 0.0,
        error_rate: float = 0.0,
        error_recovery_rate: float = 0.0,
        circular_ratio: float = 0.0,
        entropy: float = 0.0,
        num_turns: int = 0,
    ) -> tuple[str, float, dict[str, float]]:
        """Classify behavior into a category.

        Returns:
            Tuple of (category, confidence, all_scores).
        """
        scores = self.compute_scores(
            edit_ratio=edit_ratio,
            read_ratio=read_ratio,
            grep_ratio=grep_ratio,
            bash_ratio=bash_ratio,
            write_ratio=write_ratio,
            error_rate=error_rate,
            error_recovery_rate=error_recovery_rate,
            circular_ratio=circular_ratio,
            entropy=entropy,
            num_turns=num_turns,
        )
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        return best, scores[best], scores

    def get_profile(self, name: str) -> BehaviorProfile | None:
        """Get a profile by name."""
        return self.profiles.get(name)

    def list_profiles(self) -> dict[str, str]:
        """List all available profiles with descriptions."""
        return {name: p.description for name, p in self.profiles.items()}
