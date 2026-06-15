"""Generate adversarial scenarios: broken_code, failing_tests, missing_deps, network_errors."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

BROKEN_CODE_TEMPLATES: list[dict[str, str]] = [
    {"name": "off_by_one_loop", "description": "Loop iterates one time too many or too few", "language": "python",
     "code": "def find_index(items, target):\n    for i in range(len(items)):\n        if items[i] == target:\n            return i\n    return -1\n\n# Bug: range(len(items)) should handle edge case where target is last item",
     "expected_fix": "Handle edge cases in loop boundaries"},
    {"name": "null_deref", "description": "Null/None reference without checking", "language": "python",
     "code": "def get_name(user):\n    return user.name.upper()\n\n# Bug: user could be None",
     "expected_fix": "Add null check before accessing attributes"},
    {"name": "type_confusion", "description": "Function receives wrong type", "language": "python",
     "code": "def calculate_total(prices):\n    return sum(prices)\n\n# Bug: prices might contain strings",
     "expected_fix": "Validate and convert input types"},
    {"name": "infinite_recursion", "description": "Recursive function without proper base case", "language": "python",
     "code": "def fibonacci(n):\n    return fibonacci(n - 1) + fibonacci(n - 2)\n\n# Bug: No base case",
     "expected_fix": "Add base case for n <= 1"},
    {"name": "race_condition", "description": "Shared mutable state without locking", "language": "python",
     "code": "class Counter:\n    def __init__(self):\n        self.count = 0\n    \n    def increment(self):\n        self.count += 1\n\n# Bug: Not thread-safe",
     "expected_fix": "Add thread-safe locking"},
    {"name": "incorrect_comparison", "description": "Using = instead of == in comparison", "language": "python",
     "code": "def check_admin(user):\n    if user.role = 'admin':\n        return True\n    return False\n\n# Bug: Assignment instead of comparison",
     "expected_fix": "Use == for comparison, not ="},
    {"name": "missing_import", "description": "Code uses module without importing it", "language": "python",
     "code": "def get_current_time():\n    return datetime.now()\n\n# Bug: datetime module not imported",
     "expected_fix": "Add 'from datetime import datetime'"},
    {"name": "swallowed_exception", "description": "Bare except that hides errors", "language": "python",
     "code": "def read_config(path):\n    try:\n        with open(path) as f:\n            return json.load(f)\n    except:\n        return {}\n\n# Bug: Catches ALL exceptions silently",
     "expected_fix": "Catch specific exceptions and log errors"},
]

FAILING_TEST_TEMPLATES: list[dict[str, str]] = [
    {"name": "flaky_test", "description": "Test that fails intermittently due to timing or ordering", "language": "python",
     "code": "def test_api_response():\n    response = api.get('/users')\n    assert response.status_code == 200\n    assert len(response.json()) > 0\n\n# Bug: Fails when API is slow or returns empty DB",
     "expected_fix": "Add retries, mock API, or make assertions more robust"},
    {"name": "hardcoded_path", "description": "Test uses hardcoded file paths", "language": "python",
     "code": "def test_read_file():\n    content = read_file('/Users/dev/data.txt')\n    assert content is not None\n\n# Bug: Path doesn't exist on other machines",
     "expected_fix": "Use tmp_path fixture or relative paths"},
    {"name": "missing_mock", "description": "Test calls real external service", "language": "python",
     "code": "def test_send_email():\n    result = send_email('test@example.com', 'Subject', 'Body')\n    assert result.success\n\n# Bug: Sends real emails in tests",
     "expected_fix": "Mock the email sending function"},
]

MISSING_DEPS_TEMPLATES: list[dict[str, str]] = [
    {"name": "missing_package", "description": "Import fails because package isn't installed", "language": "python",
     "code": "import pandas as pd\nimport numpy as np\n\ndef process_data(data):\n    return pd.DataFrame(data).describe()\n\n# Bug: pandas and numpy not in requirements.txt",
     "expected_fix": "Add pandas and numpy to requirements.txt"},
    {"name": "version_conflict", "description": "Two packages require different versions", "language": "python",
     "code": "# requirements.txt:\n# fastapi==0.100.0\n# pydantic==1.10.0\n# Bug: fastapi 0.100 requires pydantic v2",
     "expected_fix": "Upgrade pydantic to v2 or downgrade fastapi"},
]

NETWORK_ERROR_TEMPLATES: list[dict[str, str]] = [
    {"name": "connection_timeout", "description": "API call times out without retry", "language": "python",
     "code": "import requests\n\ndef fetch_data(url):\n    return requests.get(url).json()\n\n# Bug: No timeout, no retry, no error handling",
     "expected_fix": "Add timeout, retry logic, and proper error handling"},
    {"name": "dns_failure", "description": "DNS resolution fails silently", "language": "python",
     "code": "def get_service_url(service_name):\n    return f'http://{service_name}:8080'\n\n# Bug: No DNS resolution check",
     "expected_fix": "Add DNS resolution check and fallback URLs"},
    {"name": "ssl_error", "description": "SSL certificate verification fails", "language": "python",
     "code": "import requests\n\ndef fetch_secure(url):\n    return requests.get(url, verify=False).json()\n\n# Bug: Disabling SSL verification is insecure",
     "expected_fix": "Fix SSL certificates instead of disabling verification"},
]


@dataclass
class Scenario:
    """A single adversarial test scenario."""

    name: str
    category: str
    description: str
    language: str
    code: str
    expected_fix: str
    difficulty: str = "medium"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "language": self.language,
            "code": self.code,
            "expected_fix": self.expected_fix,
            "difficulty": self.difficulty,
            "tags": self.tags,
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False)


class ScenarioGenerator:
    """Generate adversarial scenarios for testing coding agents.

    Creates scenarios in four categories:
    - broken_code: Code with bugs the agent must fix
    - failing_tests: Tests that fail and need fixing
    - missing_deps: Missing or conflicting dependencies
    - network_errors: Network-related failures
    """

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.categories = {
            "broken_code": BROKEN_CODE_TEMPLATES,
            "failing_tests": FAILING_TEST_TEMPLATES,
            "missing_deps": MISSING_DEPS_TEMPLATES,
            "network_errors": NETWORK_ERROR_TEMPLATES,
        }

    def generate(self, category: str | None = None, count: int = 10, difficulty: str | None = None) -> list[Scenario]:
        """Generate adversarial scenarios.

        Args:
            category: Optional category filter.
            count: Number of scenarios to generate.
            difficulty: Optional difficulty filter (easy, medium, hard).

        Returns:
            List of Scenario objects.
        """
        difficulties = ["easy", "medium", "hard"]
        scenarios: list[Scenario] = []

        templates = {category: self.categories[category]} if category else self.categories

        for i in range(count):
            cat = self.rng.choice(list(templates.keys())) if not category else category
            template = self.rng.choice(templates[cat])
            diff = difficulty or self.rng.choice(difficulties)

            # Add variation to the code
            varied_code = self._add_variation(template["code"], diff)

            scenario = Scenario(
                name=template["name"],
                category=cat,
                description=template["description"],
                language=template.get("language", "python"),
                code=varied_code,
                expected_fix=template["expected_fix"],
                difficulty=diff,
                tags=[cat, diff, template.get("language", "python")],
            )
            scenarios.append(scenario)

        return scenarios

    def _add_variation(self, code: str, difficulty: str) -> str:
        """Add difficulty-based variation to scenario code."""
        if difficulty == "easy":
            return code
        elif difficulty == "medium":
            # Add misleading comments
            lines = code.split("\n")
            if len(lines) > 2:
                insert_pos = self.rng.randint(1, len(lines) - 2)
                lines.insert(insert_pos, "    # This line looks suspicious but is correct")
            return "\n".join(lines)
        else:
            # Add red herrings and noise
            lines = code.split("\n")
            noise_lines = [
                "import logging",
                "logging.basicConfig(level=logging.DEBUG)",
                "# TODO: refactor this later",
                "# NOTE: performance optimization needed",
            ]
            for _ in range(2):
                pos = self.rng.randint(0, len(lines))
                lines.insert(pos, self.rng.choice(noise_lines))
            return "\n".join(lines)

    def generate_all(self) -> list[Scenario]:
        """Generate the complete scenario suite (50+ scenarios).

        Returns:
            List of all scenarios across all categories.
        """
        scenarios = []
        # Static scenarios from templates
        for cat, templates in self.categories.items():
            for template in templates:
                for diff in ["easy", "medium", "hard"]:
                    scenarios.append(Scenario(
                        name=f"{template['name']}_{diff}",
                        category=cat,
                        description=template["description"],
                        language=template.get("language", "python"),
                        code=self._add_variation(template["code"], diff),
                        expected_fix=template["expected_fix"],
                        difficulty=diff,
                        tags=[cat, diff],
                    ))
        # Additional random scenarios
        scenarios.extend(self.generate(count=10))
        return scenarios

    def save_scenarios(self, scenarios: list[Scenario], output_dir: str | Path) -> list[Path]:
        """Save scenarios as YAML files organized by category.

        Args:
            scenarios: List of Scenario objects.
            output_dir: Base directory for output.

        Returns:
            List of paths to saved files.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for scenario in scenarios:
            cat_dir = output_dir / scenario.category
            cat_dir.mkdir(parents=True, exist_ok=True)
            path = cat_dir / f"{scenario.name}.yaml"
            with open(path, "w") as f:
                f.write(scenario.to_yaml())
            paths.append(path)

        return paths
