"""ErrorRecovery-Engine: Self-healing agent middleware."""

from error_recovery.error_classifier import ErrorCategory, ErrorClassifier
from error_recovery.middleware import ErrorRecoveryMiddleware
from error_recovery.models import ErrorPattern, ErrorRecoveryConfig, RecoveryResult
from error_recovery.pattern_matcher import PatternMatcher
from error_recovery.recovery_engine import ErrorRecoveryEngine

__version__ = "0.1.0"
__all__ = [
    "ErrorPattern",
    "RecoveryResult",
    "ErrorRecoveryConfig",
    "ErrorClassifier",
    "ErrorCategory",
    "PatternMatcher",
    "ErrorRecoveryEngine",
    "ErrorRecoveryMiddleware",
]
