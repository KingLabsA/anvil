"""Tests for Anvil permission system — pattern specificity, checking, priorities."""

import pytest

from anvil.permissions.permissions import (
    PermissionAction,
    PermissionConfig,
    PermissionManager,
    _action_priority,
    _parse_action,
    _pattern_specificity,
)

# ---------------------------------------------------------------------------
# Pattern specificity
# ---------------------------------------------------------------------------

class TestPatternSpecificity:
    def test_exact_name_high(self):
        assert _pattern_specificity("bash") == 1000

    def test_exact_name_with_underscore(self):
        assert _pattern_specificity("bash_git") == 1000

    def test_exact_full_name(self):
        assert _pattern_specificity("bash_git_push") == 1000

    def test_exact_file_read(self):
        assert _pattern_specificity("file_read") == 1000

    def test_prefix_wildcard(self):
        assert _pattern_specificity("bash_*") == 105

    def test_longer_prefix_wildcard_higher(self):
        assert _pattern_specificity("bash_git_*") > _pattern_specificity("bash_*")

    def test_glob_wildcard_lowest(self):
        assert _pattern_specificity("*") == 0

    def test_question_mark_pattern(self):
        assert _pattern_specificity("?ash") == 104

    def test_longer_exact_same_category(self):
        assert _pattern_specificity("bash_git_push") == _pattern_specificity("bash")


# ---------------------------------------------------------------------------
# Action priority
# ---------------------------------------------------------------------------

class TestActionPriority:
    def test_deny_highest(self):
        assert _action_priority(PermissionAction.DENY) > _action_priority(PermissionAction.ASK)

    def test_ask_medium(self):
        assert _action_priority(PermissionAction.ASK) > _action_priority(PermissionAction.ALLOW)

    def test_allow_lowest(self):
        assert _action_priority(PermissionAction.ALLOW) == 0

    def test_deny_greater_than_allow(self):
        assert _action_priority(PermissionAction.DENY) > _action_priority(PermissionAction.ALLOW)


# ---------------------------------------------------------------------------
# Parse action from string
# ---------------------------------------------------------------------------

class TestParseAction:
    def test_parse_allow(self):
        assert _parse_action("allow") == PermissionAction.ALLOW

    def test_parse_ask(self):
        assert _parse_action("ask") == PermissionAction.ASK

    def test_parse_deny(self):
        assert _parse_action("deny") == PermissionAction.DENY

    def test_parse_case_insensitive(self):
        assert _parse_action("ALLOW") == PermissionAction.ALLOW

    def test_parse_unknown_raises_valueerror(self):
        with pytest.raises(ValueError):
            _parse_action("unknown")

    def test_parse_none_raises_valueerror(self):
        with pytest.raises(ValueError):
            _parse_action(None)


# ---------------------------------------------------------------------------
# PermissionManager: check_permission
# ---------------------------------------------------------------------------

class TestPermissionManagerCheck:
    def setup_method(self):
        self.pm = PermissionManager(PermissionConfig(rules={
            "bash": PermissionAction.ALLOW,
            "bash_*": PermissionAction.ASK,
            "file_read": PermissionAction.ALLOW,
        }))

    def test_exact_match_allowed(self):
        assert self.pm.check_permission("bash", {}) == PermissionAction.ALLOW

    def test_wildcard_match_ask(self):
        assert self.pm.check_permission("bash_git", {}) == PermissionAction.ASK

    def test_no_match_denied(self):
        assert self.pm.check_permission("unknown_tool", {}) == PermissionAction.DENY

    def test_file_read_allowed(self):
        assert self.pm.check_permission("file_read", {}) == PermissionAction.ALLOW

    def test_is_denied_method(self):
        assert self.pm.is_denied("unknown_tool", {}) is True

    def test_is_denied_for_allowed(self):
        assert self.pm.is_denied("bash", {}) is False

    def test_needs_confirmation(self):
        assert self.pm.needs_confirmation("bash_git", {}) is True

    def test_needs_no_confirmation_for_allowed(self):
        assert self.pm.needs_confirmation("bash", {}) is False

    def test_needs_no_confirmation_for_denied(self):
        assert self.pm.needs_confirmation("unknown_tool", {}) is False


# ---------------------------------------------------------------------------
# PermissionManager: default config
# ---------------------------------------------------------------------------

class TestDefaultPermissions:
    def setup_method(self):
        self.pm = PermissionManager()

    def test_default_allows_common_tools(self):
        assert self.pm.check_permission("bash", {}) == PermissionAction.ALLOW

    def test_default_allows_unknown(self):
        assert self.pm.check_permission("very_dangerous_tool", {}) == PermissionAction.ALLOW

    def test_is_denied_convenience(self):
        pm_restrictive = PermissionManager(PermissionConfig(rules={
            "very_dangerous_tool": PermissionAction.DENY,
        }))
        assert pm_restrictive.is_denied("very_dangerous_tool", {}) is True


# ---------------------------------------------------------------------------
# PermissionConfig
# ---------------------------------------------------------------------------

class TestPermissionConfig:
    def test_empty_rules(self):
        config = PermissionConfig(rules={})
        assert len(config.rules) == 0

    def test_with_rules(self):
        config = PermissionConfig(rules={"bash": PermissionAction.ALLOW})
        assert len(config.rules) == 1

    def test_config_to_dict(self):
        config = PermissionConfig(rules={"bash": PermissionAction.ALLOW})
        d = config.to_dict()
        assert "bash" in d
