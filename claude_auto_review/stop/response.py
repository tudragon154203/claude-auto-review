import json
import sys


def approve_response(message=""):
    print(
        json.dumps(
            {
                "decision": "approve",
                "reason": message,
            },
            separators=(",", ":"),
        ),
    )


def block_response(message, feedback):
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
