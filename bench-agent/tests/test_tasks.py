"""Unit tests for task definitions."""


from bench_agent.models import Difficulty, Task, TaskCategory
from bench_agent.tasks import (
    ALL_TASKS,
    BASH_TASKS,
    EDIT_TASKS,
    ERROR_RECOVERY_TASKS,
    MULTI_TOOL_TASKS,
    READ_TASKS,
    WRITE_TASKS,
    TASKS_BY_CATEGORY,
    TASKS_BY_ID,
    get_all_task_ids,
    get_task,
    get_tasks_by_category,
)


class TestTaskModels:
    def test_task_creation(self):
        task = Task(
            task_id="test-001",
            category=TaskCategory.BASH,
            difficulty=Difficulty.EASY,
            description="Test task",
            initial_state={"file.txt": "hello"},
            expected_outcome={"file_exists": ["file.txt"]},
            tools_required=["bash"],
            max_turns=5,
        )
        assert task.task_id == "test-001"
        assert task.category == TaskCategory.BASH
        assert task.difficulty == Difficulty.EASY

    def test_task_default_values(self):
        task = Task(
            task_id="test-002",
            category=TaskCategory.READ,
            difficulty=Difficulty.MEDIUM,
            description="Read task",
        )
        assert task.initial_state == {}
        assert task.expected_outcome == {}
        assert task.tools_required == []
        assert task.max_turns == 10
        assert task.verification_script == ""


class TestTaskCategories:
    def test_bash_tasks_exist(self):
        assert len(BASH_TASKS) >= 20
        for task in BASH_TASKS:
            assert task.category == TaskCategory.BASH

    def test_edit_tasks_exist(self):
        assert len(EDIT_TASKS) >= 20
        for task in EDIT_TASKS:
            assert task.category == TaskCategory.EDIT

    def test_read_tasks_exist(self):
        assert len(READ_TASKS) >= 15
        for task in READ_TASKS:
            assert task.category == TaskCategory.READ

    def test_write_tasks_exist(self):
        assert len(WRITE_TASKS) >= 15
        for task in WRITE_TASKS:
            assert task.category == TaskCategory.WRITE

    def test_multi_tool_tasks_exist(self):
        assert len(MULTI_TOOL_TASKS) >= 15
        for task in MULTI_TOOL_TASKS:
            assert task.category == TaskCategory.MULTI_TOOL

    def test_error_recovery_tasks_exist(self):
        assert len(ERROR_RECOVERY_TASKS) >= 15
        for task in ERROR_RECOVERY_TASKS:
            assert task.category == TaskCategory.ERROR_RECOVERY

    def test_total_task_count(self):
        assert len(ALL_TASKS) >= 100

    def test_category_correctness(self):
        for task in ALL_TASKS:
            assert task.category in list(TaskCategory)

    def test_difficulty_distribution(self):
        difficulties = [t.difficulty for t in ALL_TASKS]
        assert Difficulty.EASY in difficulties
        assert Difficulty.MEDIUM in difficulties
        assert Difficulty.HARD in difficulties


class TestTaskLookup:
    def test_get_task_by_id(self):
        task = get_task("bash-001")
        assert task is not None
        assert task.task_id == "bash-001"

    def test_get_nonexistent_task(self):
        task = get_task("nonexistent-999")
        assert task is None

    def test_get_tasks_by_category(self):
        bash_tasks = get_tasks_by_category(TaskCategory.BASH)
        assert len(bash_tasks) >= 20
        for task in bash_tasks:
            assert task.category == TaskCategory.BASH

    def test_get_all_task_ids(self):
        ids = get_all_task_ids()
        assert len(ids) >= 100
        assert "bash-001" in ids

    def test_tasks_by_id_complete(self):
        for task in ALL_TASKS:
            assert TASKS_BY_ID[task.task_id] == task

    def test_tasks_by_category_complete(self):
        for cat in TaskCategory:
            assert cat in TASKS_BY_CATEGORY
            assert len(TASKS_BY_CATEGORY[cat]) > 0


class TestTaskIntegrity:
    def test_all_tasks_have_unique_ids(self):
        ids = [t.task_id for t in ALL_TASKS]
        assert len(ids) == len(set(ids)), "Duplicate task IDs found"

    def test_all_tasks_have_descriptions(self):
        for task in ALL_TASKS:
            assert task.description, f"Task {task.task_id} has no description"
            assert len(task.description) > 10, f"Task {task.task_id} has too short description"

    def test_all_tasks_have_tools_required(self):
        for task in ALL_TASKS:
            assert task.tools_required, f"Task {task.task_id} has no tools_required"

    def test_all_tasks_have_positive_max_turns(self):
        for task in ALL_TASKS:
            assert task.max_turns > 0, f"Task {task.task_id} has non-positive max_turns"

    def test_initial_state_files_are_strings(self):
        for task in ALL_TASKS:
            for filename, content in task.initial_state.items():
                assert isinstance(filename, str), f"Task {task.task_id}: filename not string"
                assert isinstance(content, str), f"Task {task.task_id}: content not string"

    def test_task_id_format(self):
        for task in ALL_TASKS:
            parts = task.task_id.split("-")
            assert len(parts) >= 2, f"Task ID {task.task_id} has wrong format"
            assert parts[0] in [
                "bash", "edit", "read", "write", "multi", "error"
            ], f"Task ID {task.task_id} has unknown prefix"
