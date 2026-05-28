from __future__ import annotations

from enum import Enum


class AutocompleteStatus(str, Enum):
    OUTPUT_WRITTEN = "output_written"
    CLI_NOT_FOUND = "cli_not_found"
    PROMPT_NOT_FOUND = "prompt_not_found"
    TIMEOUT = "timeout"
    ERROR = "error"
    NONZERO = "nonzero"
    EMPTY_STDOUT = "empty_stdout"


class StopAllowReason(str, Enum):
    DISABLED = "disabled"
    NO_UNREVIEWED_FILES = "no_unreviewed_files"
    CIRCUIT_BREAKER = "circuit_breaker"
    CLASSIFIER_INCOMPLETE = "classifier_incomplete"
    NO_UNREVIEWED_AFTER_REVIEW = "no_unreviewed_files_after_review"
