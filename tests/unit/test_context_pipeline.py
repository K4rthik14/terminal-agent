"""Unit tests for state-driven context selection."""

from context.conversation import ConversationSelector
from context.files import RelevantFileSelector
from context.goal import GoalExtractor
from context.manager import ContextManager
from context.models import AgentState
from context.tools import RelevantToolSelector
from tools.bash import BashTool
from tools.file_read import ReadFileTool
from tools.file_write import WriteFileTool
from utils.types import MessageList


def test_goal_extractor_returns_latest_user_goal() -> None:
    state = AgentState(
        messages=[
            {"role": "user", "content": "old task"},
            {"role": "assistant", "content": "done"},
            {"role": "user", "content": "Read src/main.py"},
        ]
    )

    assert GoalExtractor().extract(state) == "Read src/main.py"


def test_file_selector_extracts_explicit_paths() -> None:
    state = AgentState(messages=[])

    assert RelevantFileSelector().select("Update src/main.py and tests/test_main.py", state) == [
        "src/main.py",
        "tests/test_main.py",
    ]


def test_tool_selector_keeps_tools_relevant_to_goal() -> None:
    tools = [ReadFileTool(), WriteFileTool(), BashTool()]
    state = AgentState(messages=[])

    selected = RelevantToolSelector().select("Create a file and run pytest", tools, state)

    assert [tool.name for tool in selected] == ["read_file", "write_file", "bash"]


def test_conversation_selector_excludes_stale_system_messages() -> None:
    messages: MessageList = [
        {"role": "system", "content": "stale"},
        {"role": "user", "content": "current task"},
    ]

    selected = ConversationSelector(max_messages=4).select(AgentState(messages=messages))

    assert selected == [{"role": "user", "content": "current task"}]


def test_context_manager_builds_fresh_system_context() -> None:
    state = AgentState(
        messages=[
            {"role": "system", "content": "stale system"},
            {"role": "user", "content": "Read README.md"},
        ]
    )

    selection = ContextManager().build(state, [ReadFileTool(), WriteFileTool()])

    assert selection.messages[0]["role"] == "system"
    assert "Current task:" in selection.messages[0]["content"]
    assert "README.md" in selection.relevant_files
    assert selection.selected_tools == ["read_file"]
