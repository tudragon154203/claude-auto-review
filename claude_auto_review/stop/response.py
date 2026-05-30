from __future__ import annotations

import json
import sys
from typing import Protocol, runtime_checkable


@runtime_checkable
class ResponseEmitter(Protocol):
    def approve(self, message: str = "") -> None: ...
    def block(self, message: str, feedback: str) -> None: ...


class StdoutResponseEmitter:
    def approve(self, message: str = "") -> None:
        print(json.dumps({"systemMessage": message}, separators=(",", ":")))
        if message:
            print(message, file=sys.stderr)

    def block(self, message: str, feedback: str) -> None:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": feedback,
                    "systemMessage": message,
                },
                separators=(",", ":"),
            ),
        )
        print(message, file=sys.stderr)


_default_emitter = StdoutResponseEmitter()


def approve_response(message=""):
    _default_emitter.approve(message)


def block_response(message, feedback):
    _default_emitter.block(message, feedback)
