import json
import sys


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
