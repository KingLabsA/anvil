"""Tests for Anvil permission system — PermissionAction, PermissionConfig, PermissionManager."""

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
# PermissionAction enum
# ---------------------------------------------------------------------------

class TestPermissionAction:
    def test_allow_value(self):
        assert PermissionAction.ALLOW.value == "allow"

    def test_ask_value(self):
        assert PermissionAction.ASK.value == "ask"

    def test_deny_value(self):
        assert PermissionAction.DENY.value == "deny"

    def test_from_string(self):
        assert PermissionAction("allow") == PermissionAction.ALLOW
        assert PermissionAction("ask") == PermissionAction.ASK
        assert PermissionAction("deny") == PermissionAction.DENY

    def test_from_string_case_insensitive(self):
        assert _parse_action("ALLOW") == PermissionAction.ALLOW
        assert _parse_action("Ask") == PermissionAction.ASK
        assert _parse_action("Deny") == PermissionAction.DENY


# ---------------------------------------------------------------------------
# _parse_action helper
# ---------------------------------------------------------------------------

class TestParseAction:
    def test_parse_string_allow(self):
        assert _parse_action("allow") == PermissionAction.ALLOW

    def test_parse_string_ask(self):
        assert _parse_action("ask") == PermissionAction.ASK

    def test_parse_string_deny(self):
        assert _parse_action("deny") == PermissionAction.DENY

    def test_parse_permission_action(self):
        assert _parse_action(PermissionAction.ALLOW) == PermissionAction.ALLOW
        assert _parse_action(PermissionAction.DENY) == PermissionAction.DENY

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_action(42)

    def test_parse_mixed_case_string(self):
        assert _parse_action("  ALLOW  ") == PermissionAction.ALLOW


# ---------------------------------------------------------------------------
# _action_priority helper
# ---------------------------------------------------------------------------

class TestActionPriority:
    def test_allow_lowest(self):
        assert _action_priority(PermissionAction.ALLOW) < _action_priority(PermissionAction.ASK)

    def test_ask_middle(self):
        assert _action_priority(PermissionAction.ASK) < _action_priority(PermissionAction.DENY)

    def test_deny_highest(self):
        assert _action_priority(PermissionAction.DENY) > _action_priority(PermissionAction.ASK)


# ---------------------------------------------------------------------------
# _pattern_specificity helper
# ---------------------------------------------------------------------------

class TestPatternSpecificity:
    def test_wildcard_lowest(self):
        assert _pattern_specificity("*") == 0

    def test_exact_name_highest(self):
        assert _pattern_specificity("bash") == 100

    def test_prefix_wildcard_medium(self):
        specificity = _pattern_specificity("bash_*")
        assert 0 < specificity < 100

    def test_longer_prefix_higher(self):
        assert _pattern_specificity("bash_git_push") > _pattern_specificity("bash_git")

    def test_question_mark_pattern(self):
        assert _pattern_specificity("bas?") == 100


# ---------------------------------------------------------------------------
# PermissionConfig creation with tool permissions
# ---------------------------------------------------------------------------

class TestPermissionConfig:
    def test_default_empty_config(self):
        cfg = PermissionConfig()
        assert cfg.rules == {}

    def test_permissive_config(self):
        cfg = PermissionConfig.permissive()
        assert PermissionAction.ALLOW in cfg.rules.values()

    def test_readonly_config(self):
        cfg = PermissionConfig.readonly()
        assert cfg.rules.get("read") == PermissionAction.ALLOW
        assert cfg.rules.get("write") == PermissionAction.DENY
        assert cfg.rules.get("bash") == PermissionAction.DENY

    def test_strict_config(self):
        cfg = PermissionConfig.strict()
        assert cfg.rules.get("read") == PermissionAction.ALLOW
        assert cfg.rules.get("write") == PermissionAction.ASK

    def test_custom_rules(self):
        cfg = PermissionConfig(rules={
            "read": PermissionAction.ALLOW,
            "bash git status *": PermissionAction.ALLOW,
            "bash": PermissionAction.ASK,
            "write": PermissionAction.DENY,
        })
        assert cfg.rules["read"] == PermissionAction.ALLOW
        assert cfg.rules["write"] == PermissionAction.DENY

    def test_to_dict(self):
        cfg = PermissionConfig(rules={"read": PermissionAction.ALLOW, "write": PermissionAction.DENY})
        d = cfg.to_dict()
        assert d["read"] == "allow"
        assert d["write"] == "deny"

    def test_from_dict(self):
        data = {"read": "allow", "write": "deny"}
        cfg = PermissionConfig.from_dict(data)
        assert cfg.rules["read"] == "allow"
        assert cfg.rules["write"] == "deny"

    def test_from_dict_with_permission_action(self):
        data = {"read": PermissionAction.ALLOW}
        cfg = PermissionConfig.from_dict(data)
        assert cfg.rules["read"] == PermissionAction.ALLOW

    def test_from_dict_invalid_value_raises(self):
        with pytest.raises(ValueError):
            PermissionConfig.from_dict({"read": 42})

    def test_glob_patterns(self):
        cfg = PermissionConfig(rules={
            "mymcp_*": PermissionAction.ALLOW,
            "*": PermissionAction.DENY,
        })
        assert cfg.rules["mymcp_*"] == PermissionAction.ALLOW
        assert cfg.rules["*"] == PermissionAction.DENY


# ---------------------------------------------------------------------------
# bash command-level permissions
# ---------------------------------------------------------------------------

class TestBashCommandPermissions:
    def test_bash_git_status_allowed(self):
        mgr = PermissionManager(PermissionConfig(rules={
            "bash git status *": PermissionAction.ALLOW,
            "bash git push *": PermissionAction.ASK,
            "bash *": PermissionAction.DENY,
        }))
        assert mgr.check_permission("bash", {"command": "git status"}) == PermissionAction.ALLOW

    def test_bash_git_push_ask(self):
        mgr = PermissionManager(PermissionConfig(rules={
            "bash git status *": PermissionAction.ALLOW,
            "bash git push *": PermissionAction.ASK,
            "bash *": PermissionAction.DENY,
        }))
        assert mgr.check_permission("bash", {"command": "git push origin main"}) == PermissionAction.ASK

    def test_bash_wildcard_deny(self):
        mgr = PermissionManager(PermissionConfig(rules={
            "bash git status *": PermissionAction.ALLOW,
            "bash git push *": PermissionAction.ASK,
            "bash *": PermissionAction.DENY,
        }))
        assert mgr.check_permission("bash", {"command": "rm -rf /tmp"}) == PermissionAction.DENY


# ---------------------------------------------------------------------------
# Resolution: most specific match wins
# ---------------------------------------------------------------------------

class TestResolutionSpecificity:
    def test_exact_match_beats_wildcard(self):
        mgr = PermissionManager(PermissionConfig(rules={
            "read": PermissionAction.ALLOW,
            "*": PermissionAction.DENY,
        }))
        assert mgr.check_permission("read", {}) == PermissionAction.ALLOW
        assert mgr.check_permission("unknown_tool", {}) == PermissionAction.DENY


# ---------------------------------------------------------------------------
# Last matching rule takes precedence
# ---------------------------------------------------------------------------

class TestLastMatchPrecedence:
    def test_last_rule_overrides(self):
        mgr = PermissionManager(PermissionConfig(rules={
            "read": PermissionAction.ALLOW,
            "read": PermissionAction.DENY,
        }))
        assert mgr.check_permission("read", {}) == PermissionAction.DENY


# ---------------------------------------------------------------------------
# Per-agent permissions override global
# ---------------------------------------------------------------------------

class TestPerAgentOverride:
    def test_agent_config_overrides_global(self):
        global_cfg = PermissionConfig(rules={"*": PermissionAction.ALLOW})
        agent_cfg = PermissionConfig(rules={"bash": PermissionAction.DENY})
        mgr = PermissionManager(global_cfg)
        assert mgr.check_permission("bash", {}, agent_cfg) == PermissionAction.DENY

    def test_global_allows_agent_denies(self):
        global_cfg = PermissionConfig.permissive()
        agent_cfg = PermissionConfig(rules={"write": PermissionAction.ASK})
        mgr = PermissionManager(global_cfg)
        assert mgr.is_allowed("read", {}, agent_cfg)
        assert mgr.needs_confirmation("write", {}, agent_cfg)


# ---------------------------------------------------------------------------
# Wildcard matching (* matches everything)
# ---------------------------------------------------------------------------

class TestWildcardMatching:
    def test_wildcard_allows_all(self):
        mgr = PermissionManager(PermissionConfig.permissive())
        assert mgr.is_allowed("bash", {"command": "anything"})
        assert mgr.is_allowed("write", {})
        assert mgr.is_allowed("read", {})

    def test_wildcard_denies_all(self):
        mgr = PermissionManager(PermissionConfig(rules={"*": PermissionAction.DENY}))
        assert mgr.is_denied("bash", {"command": "ls"})
        assert mgr.is_denied("read", {})


# ---------------------------------------------------------------------------
# Default: allow all
# ---------------------------------------------------------------------------

class TestDefaultAllowAll:
    def test_default_permissive_allows_all(self):
        mgr = PermissionManager(PermissionConfig.permissive())
        for tool in ["bash", "read", "write", "edit", "grep", "glob", "ls"]:
            assert mgr.is_allowed(tool, {})

    def test_is_allowed_convenience(self):
        mgr = PermissionManager(PermissionConfig.permissive())
        assert mgr.is_allowed("bash", {"command": "ls"})

    def test_needs_confirmation_convenience(self):
        mgr = PermissionManager(PermissionConfig(rules={"write": PermissionAction.ASK}))
        assert mgr.needs_confirmation("write", {})
        assert not mgr.needs_confirmation("read", {})

    def test_is_denied_convenience(self):
        mgr = PermissionManager(PermissionConfig(rules={"bash": PermissionAction.DENY}))
        assert mgr.is_denied("bash", {"command": "rm -rf /"})
        assert not mgr.is_denied("read", {})

    def test_unknown_tool_default_permissive(self):
        mgr = PermissionManager(PermissionConfig.permissive())
        assert mgr.check_permission("unknown_tool", {}) == PermissionAction.ALLOW

    def test_unknown_tool_default_deny(self):
        mgr = PermissionManager(PermissionConfig(rules={"*": PermissionAction.DENY}))
        assert mgr.check_permission("unknown_tool", {}) == PermissionAction.DENY
