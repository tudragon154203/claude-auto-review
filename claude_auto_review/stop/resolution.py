from dataclasses import dataclass


@dataclass(frozen=True)
class StopFlowResolution:
    state: list
    unreviewed: list
    review: dict | None = None
    exit_code: int | None = None

    @property
    def is_terminal(self):
        return self.exit_code is not None
