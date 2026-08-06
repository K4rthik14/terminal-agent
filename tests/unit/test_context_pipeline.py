"""Unit tests for state-driven context selection."""

from context.conversation import ConversationSelector
from context.files import RelevantFileSelector
from context.goal import GoalExtractor
from context.manager import ContextManager
from context.models import ContextState
from context.tools import RelevantToolSelector
from tools.bash import BashTool
from tools.file_read import ReadFileTool
from tools.file_write import WriteFileTool
from utils.types import MessageList


def test_goal_extractor_returns_current_goal() -> None:
    state = ContextState(goal="  Read   src/main.py  ")

    assert GoalExtractor().extract(state) == "Read src/main.py"


def test_goal_extractor_falls_back_to_latest_user_message() -> None:
    state = ContextState(
        conversation_tail=[
            {"role": "user", "content": "old request"},
            {"role": "assistant", "content": "acknowledged"},
            {"role": "user", "content": "Create tests for the parser"},
        ]
    )

    assert GoalExtractor().extract(state) == "Create tests for the parser"


def test_goal_extractor_compacts_long_goals() -> None:
    state = ContextState(goal="one two three four five six")

    assert GoalExtractor(max_length=12).extract(state) == "one two thr…"


def test_file_selector_extracts_explicit_paths() -> None:
    state = ContextState(goal="Update src/main.py and tests/test_main.py")

    assert RelevantFileSelector().select(state) == [
        "src/main.py",
        "tests/test_main.py",
    ]


def test_file_selector_uses_active_hints_without_reading_history() -> None:
    state = ContextState(
        goal="Review README.md",
        active_files=("src/agent.py",),
        conversation_tail=[
            {"role": "user", "content": "Ignore unrelated.py"},
        ],
    )

    assert RelevantFileSelector().select(state) == ["src/agent.py", "README.md"]


def test_tool_selector_keeps_tools_relevant_to_goal() -> None:
    tools = [ReadFileTool(), WriteFileTool(), BashTool()]
    state = ContextState()

    selected = RelevantToolSelector().select("Create a file and run pytest", tools, state)

    assert [tool.name for tool in selected] == ["read_file", "write_file", "bash"]


def test_conversation_selector_excludes_stale_system_messages() -> None:
    messages: MessageList = [
        {"role": "system", "content": "stale"},
        {"role": "user", "content": "current task"},
    ]

    selected = ConversationSelector(max_messages=4).select(
        ContextState(conversation_tail=messages[1:])
    )

    assert selected == [{"role": "user", "content": "current task"}]


def test_context_manager_builds_fresh_system_context() -> None:
    state = ContextState(
        goal="Read README.md",
        conversation_tail=[{"role": "user", "content": "Read README.md"}],
    )

    selection = ContextManager().build(state, [ReadFileTool(), WriteFileTool()])

    assert selection.messages[0]["role"] == "system"
    assert "Current task:" in selection.messages[0]["content"]
    assert "README.md" in selection.relevant_files
    assert selection.selected_tools == ["read_file"]
