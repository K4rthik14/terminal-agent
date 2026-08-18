"""RLM (Reasoning Language Model) pre-execution reasoning phase.

Provides a bounded, read-only reasoning controller that produces
an execution brief before the main agent acts on a task.
"""

from rlm.controller import RLMController, RLMResult

__all__ = ["RLMController", "RLMResult"]
