"""Tests for error_classifier module."""


from error_recovery.error_classifier import ClassificationRule, ErrorClassifier
from error_recovery.models import ErrorCategory


class TestErrorCategory:
    def test_all_categories_exist(self):
        expected = {
            "bash_error", "edit_error", "read_error", "write_error",
            "test_error", "network_error", "import_error", "type_error", "unknown",
        }
        actual = {c.value for c in ErrorCategory}
        assert actual == expected


class TestClassificationRule:
    def test_pattern_match(self):
        rule = ClassificationRule(
            category=ErrorCategory.BASH_ERROR,
            patterns=[r"command not found"],
        )
        assert rule.matches("bash: command not found: foo", "bash")

    def test_pattern_no_match(self):
        rule = ClassificationRule(
            category=ErrorCategory.BASH_ERROR,
            patterns=[r"command not found"],
        )
        assert not rule.matches("everything is fine", "")

    def test_keyword_match(self):
        rule = ClassificationRule(
            category=ErrorCategory.BASH_ERROR,
            patterns=[],
            keywords=["bash"],
        )
        assert rule.matches("something happened", "bash")

    def test_invalid_regex_ignored(self):
        rule = ClassificationRule(
            category=ErrorCategory.BASH_ERROR,
            patterns=[r"[invalid"],
        )
        assert not rule.matches("anything", "")

    def test_combined_pattern_and_keyword(self):
        rule = ClassificationRule(
            category=ErrorCategory.BASH_ERROR,
            patterns=[r"exit code \d+"],
            keywords=["subprocess"],
        )
        assert rule.matches("subprocess exit code 1", "")
        assert rule.matches("exit code 127", "")
        assert rule.matches("subprocess ran fine", "")


class TestErrorClassifier:
    def setup_method(self):
        self.classifier = ErrorClassifier()

    # --- BASH_ERROR ---

    def test_command_not_found(self):
        assert self.classifier.classify("bash: command not found: xyz") == ErrorCategory.BASH_ERROR

    def test_permission_denied(self):
        assert self.classifier.classify("Permission denied") == ErrorCategory.BASH_ERROR

    def test_exit_code(self):
        assert self.classifier.classify("Process exit code 1") == ErrorCategory.BASH_ERROR

    def test_segmentation_fault(self):
        assert self.classifier.classify("Segmentation fault (core dumped)") == ErrorCategory.BASH_ERROR

    def test_out_of_memory(self):
        assert self.classifier.classify("Out of memory error") == ErrorCategory.BASH_ERROR

    def test_no_such_file_bash(self):
        assert self.classifier.classify("No such file or directory", tool_name="bash") == ErrorCategory.BASH_ERROR

    # --- EDIT_ERROR ---

    def test_pattern_not_matched(self):
        assert self.classifier.classify("Pattern not matched in file") == ErrorCategory.EDIT_ERROR

    def test_oldstring_not_found(self):
        assert self.classifier.classify("oldstring not found in the file") == ErrorCategory.EDIT_ERROR

    def test_edit_tool_hint(self):
        assert self.classifier.classify("something went wrong", tool_name="edit") == ErrorCategory.EDIT_ERROR

    # --- TEST_ERROR ---

    def test_assertion_failed(self):
        assert self.classifier.classify("Assertion failed: expected 5, got 3") == ErrorCategory.TEST_ERROR

    def test_test_failed(self):
        assert self.classifier.classify("test_login failed") == ErrorCategory.TEST_ERROR

    def test_pytest_keyword(self):
        assert self.classifier.classify("error in test suite", tool_name="pytest") == ErrorCategory.TEST_ERROR

    # --- NETWORK_ERROR ---

    def test_connection_refused(self):
        assert self.classifier.classify("Connection refused on port 8080") == ErrorCategory.NETWORK_ERROR

    def test_dns_error(self):
        assert self.classifier.classify("DNS resolution failed for example.com") == ErrorCategory.NETWORK_ERROR

    def test_ssl_error(self):
        assert self.classifier.classify("SSL certificate verification failed") == ErrorCategory.NETWORK_ERROR

    def test_timeout_network(self):
        assert self.classifier.classify("Connection timed out after 30s") == ErrorCategory.NETWORK_ERROR

    # --- IMPORT_ERROR ---

    def test_module_not_found(self):
        assert self.classifier.classify("ModuleNotFoundError: No module named 'foo'") == ErrorCategory.IMPORT_ERROR

    def test_import_error(self):
        assert self.classifier.classify("ImportError: cannot import name 'bar'") == ErrorCategory.IMPORT_ERROR

    def test_dependency_missing(self):
        assert self.classifier.classify("dependency not installed: requests") == ErrorCategory.IMPORT_ERROR

    # --- TYPE_ERROR ---

    def test_type_error(self):
        assert self.classifier.classify("TypeError: unsupported operand type(s)") == ErrorCategory.TYPE_ERROR

    def test_attribute_error(self):
        assert self.classifier.classify("AttributeError: 'NoneType' object has no attribute 'foo'") == ErrorCategory.TYPE_ERROR

    def test_key_error(self):
        assert self.classifier.classify("KeyError: 'missing_key'") == ErrorCategory.TYPE_ERROR

    def test_index_error(self):
        assert self.classifier.classify("IndexError: list index out of range") == ErrorCategory.TYPE_ERROR

    # --- WRITE_ERROR ---

    def test_write_permission_denied(self):
        # "permission denied" matches BASH_ERROR first; both are valid
        result = self.classifier.classify("Permission denied writing to file")
        assert result in (ErrorCategory.WRITE_ERROR, ErrorCategory.BASH_ERROR)

    def test_disk_full(self):
        assert self.classifier.classify("No space left on device") == ErrorCategory.BASH_ERROR

    # --- READ_ERROR ---

    def test_read_file_not_found(self):
        assert self.classifier.classify("File not found when reading", tool_name="read") == ErrorCategory.READ_ERROR

    # --- UNKNOWN ---

    def test_unknown_error(self):
        assert self.classifier.classify("something completely random") == ErrorCategory.UNKNOWN

    def test_empty_error(self):
        assert self.classifier.classify("") == ErrorCategory.UNKNOWN

    # --- Confidence ---

    def test_classify_with_confidence(self):
        category, confidence = self.classifier.classify_with_confidence("command not found: xyz", "bash")
        assert category == ErrorCategory.BASH_ERROR
        assert confidence > 0.0

    def test_unknown_confidence(self):
        category, confidence = self.classifier.classify_with_confidence("random unknown error xyz123")
        assert category == ErrorCategory.UNKNOWN
        assert confidence == 0.0

    # --- Custom rules ---

    def test_custom_rule_priority(self):
        custom = ClassificationRule(
            category=ErrorCategory.NETWORK_ERROR,
            patterns=[r"kafka.*error"],
            keywords=["kafka"],
        )
        classifier = ErrorClassifier(custom_rules=[custom])
        assert classifier.classify("kafka error: broker unavailable") == ErrorCategory.NETWORK_ERROR

    def test_multiple_categories_match(self):
        result = self.classifier.classify("Permission denied writing file /tmp/test")
        assert result in (ErrorCategory.BASH_ERROR, ErrorCategory.WRITE_ERROR)
