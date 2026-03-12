"""
Tests for AIGenerator in ai_generator.py.

These tests mock the Anthropic client to verify:
- Direct responses (stop_reason == "end_turn") are returned correctly
- Tool-use responses (stop_reason == "tool_use") trigger tool execution
- The message structure sent in the second API call is correct
- tool_manager.execute_tool() is called with the right arguments
- Sequential tool calls (up to MAX_TOOL_ROUNDS) work correctly
"""
import pytest
from unittest.mock import MagicMock, patch, call

from ai_generator import AIGenerator


@pytest.fixture
def mock_anthropic_client():
    """A mock for the anthropic.Anthropic client instance."""
    return MagicMock()


@pytest.fixture
def generator(mock_anthropic_client):
    """AIGenerator with a patched Anthropic client."""
    with patch("ai_generator.anthropic.Anthropic", return_value=mock_anthropic_client):
        gen = AIGenerator(api_key="test-key", model="test-model")
    return gen


def make_direct_response(text="Direct answer"):
    """Build a mock response with stop_reason='end_turn'."""
    response = MagicMock()
    response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.text = text
    response.content = [text_block]
    return response


def make_tool_use_response(tool_name="search_course_content", tool_input=None, tool_id="toolu_01"):
    """Build a mock response with stop_reason='tool_use' containing one tool_use block."""
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = tool_name
    tool_use_block.input = tool_input or {"query": "test query"}
    tool_use_block.id = tool_id

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_use_block]
    return response


class TestAIGeneratorDirectResponse:
    """Tests for queries answered without tool use."""

    def test_direct_response_returns_text(self, generator, mock_anthropic_client):
        """generate_response() must return the text from Claude's direct reply."""
        mock_anthropic_client.messages.create.return_value = make_direct_response("Hello!")
        result = generator.generate_response(query="Hi")
        assert result == "Hello!"

    def test_direct_response_does_not_call_tool_manager(self, generator, mock_anthropic_client):
        """tool_manager.execute_tool() must NOT be called for direct answers."""
        mock_anthropic_client.messages.create.return_value = make_direct_response()
        tool_manager = MagicMock()
        generator.generate_response(query="What is 2+2?", tool_manager=tool_manager)
        tool_manager.execute_tool.assert_not_called()

    def test_tools_included_in_first_api_call(self, generator, mock_anthropic_client):
        """The first API call must include the tools list and tool_choice='auto'."""
        mock_anthropic_client.messages.create.return_value = make_direct_response()
        tools = [{"name": "search_course_content", "description": "Search", "input_schema": {}}]
        generator.generate_response(query="test", tools=tools)

        call_kwargs = mock_anthropic_client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs.get("tool_choice") == {"type": "auto"}

    def test_system_prompt_included_in_api_call(self, generator, mock_anthropic_client):
        """The system prompt must be sent with the API call."""
        mock_anthropic_client.messages.create.return_value = make_direct_response()
        generator.generate_response(query="test")
        call_kwargs = mock_anthropic_client.messages.create.call_args[1]
        assert "system" in call_kwargs
        assert len(call_kwargs["system"]) > 0

    def test_conversation_history_appended_to_system_prompt(self, generator, mock_anthropic_client):
        """When history is provided, it must be included in the system content."""
        mock_anthropic_client.messages.create.return_value = make_direct_response()
        generator.generate_response(query="test", conversation_history="User: Hi\nAssistant: Hello")
        call_kwargs = mock_anthropic_client.messages.create.call_args[1]
        assert "User: Hi" in call_kwargs["system"]


class TestAIGeneratorToolUseFlow:
    """Tests for queries that trigger tool use (content-related questions)."""

    def test_tool_use_triggers_second_api_call(self, generator, mock_anthropic_client):
        """When Claude returns tool_use, a second API call must be made."""
        first = make_tool_use_response()
        second = make_direct_response("Final answer")
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search result text"
        generator.generate_response(query="test", tool_manager=tool_manager)

        assert mock_anthropic_client.messages.create.call_count == 2

    def test_tool_manager_execute_called_with_correct_name(self, generator, mock_anthropic_client):
        """tool_manager.execute_tool() must be called with the tool name from Claude's response."""
        first = make_tool_use_response(tool_name="search_course_content", tool_input={"query": "vectors"})
        second = make_direct_response("Final answer")
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tool_manager=tool_manager)

        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="vectors"
        )

    def test_tool_manager_execute_called_with_correct_kwargs(self, generator, mock_anthropic_client):
        """Tool input dict from Claude must be unpacked as kwargs to execute_tool()."""
        tool_input = {"query": "transformers", "course_name": "AI 101", "lesson_number": 2}
        first = make_tool_use_response(tool_input=tool_input)
        second = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tool_manager=tool_manager)

        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="transformers",
            course_name="AI 101",
            lesson_number=2,
        )

    def test_second_api_call_message_count(self, generator, mock_anthropic_client):
        """The second API call must have 3 messages: user, assistant (tool_use), user (tool_result)."""
        first = make_tool_use_response()
        second = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search result"
        generator.generate_response(query="my query", tool_manager=tool_manager)

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        assert len(messages) == 3

    def test_second_api_call_first_message_is_user_query(self, generator, mock_anthropic_client):
        """Messages[0] in the second call must be the original user message."""
        first = make_tool_use_response()
        second = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="my query", tool_manager=tool_manager)

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "my query"

    def test_second_api_call_second_message_is_assistant_tool_use(self, generator, mock_anthropic_client):
        """Messages[1] must be the assistant message containing the tool_use blocks."""
        first = make_tool_use_response()
        second = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tool_manager=tool_manager)

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        assert messages[1]["role"] == "assistant"
        # content must be the original response's content (SDK objects)
        assert messages[1]["content"] is first.content

    def test_second_api_call_third_message_is_tool_result(self, generator, mock_anthropic_client):
        """Messages[2] must be a user message whose content is a list of tool_result blocks."""
        first = make_tool_use_response(tool_id="toolu_01")
        second = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search result text"
        generator.generate_response(query="test", tool_manager=tool_manager)

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        tool_result_message = messages[2]
        assert tool_result_message["role"] == "user"
        assert isinstance(tool_result_message["content"], list)
        assert len(tool_result_message["content"]) == 1

        tool_result_block = tool_result_message["content"][0]
        assert tool_result_block["type"] == "tool_result"
        assert tool_result_block["tool_use_id"] == "toolu_01"
        assert tool_result_block["content"] == "search result text"

    def test_second_api_call_includes_tools_parameter(self, generator, mock_anthropic_client):
        """The second (follow-up) API call MUST include 'tools'.

        The Anthropic API requires the tools parameter in any call where the
        message history contains tool_use or tool_result blocks. Omitting it
        causes a BadRequestError and is the root cause of 'Query failed' errors.
        """
        first = make_tool_use_response()
        second = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tools = [{"name": "search_course_content", "description": "Search", "input_schema": {}}]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tools=tools, tool_manager=tool_manager)

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        assert "tools" in second_call_kwargs
        assert second_call_kwargs["tools"] == tools

    def test_generate_response_returns_final_answer(self, generator, mock_anthropic_client):
        """generate_response() must return the text from the second (follow-up) Claude call."""
        first = make_tool_use_response()
        second = make_direct_response("Final synthesized answer")
        mock_anthropic_client.messages.create.side_effect = [first, second]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        result = generator.generate_response(query="test", tool_manager=tool_manager)

        assert result == "Final synthesized answer"


class TestAIGeneratorSequentialToolUse:
    """Tests for queries requiring multiple sequential tool calls."""

    def test_two_sequential_tool_calls_triggers_three_api_calls(self, generator, mock_anthropic_client):
        """Two tool rounds must result in 3 total API calls: initial + round 1 + round 2."""
        r1 = make_tool_use_response(tool_id="toolu_01")
        r2 = make_tool_use_response(tool_id="toolu_02")
        final = make_direct_response("Final after 2 rounds")
        mock_anthropic_client.messages.create.side_effect = [r1, r2, final]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search result"
        result = generator.generate_response(query="test", tool_manager=tool_manager)

        assert mock_anthropic_client.messages.create.call_count == 3
        assert result == "Final after 2 rounds"

    def test_two_sequential_tool_calls_executes_tool_twice(self, generator, mock_anthropic_client):
        """execute_tool() must be called once per tool round."""
        r1 = make_tool_use_response(tool_id="toolu_01")
        r2 = make_tool_use_response(tool_id="toolu_02")
        final = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [r1, r2, final]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tool_manager=tool_manager)

        assert tool_manager.execute_tool.call_count == 2

    def test_round_limit_stops_at_max_rounds(self, generator, mock_anthropic_client):
        """When Claude requests a 3rd tool call, the loop must stop after 2 rounds."""
        r1 = make_tool_use_response(tool_id="toolu_01")
        r2 = make_tool_use_response(tool_id="toolu_02")
        # The third response still has stop_reason="tool_use" but the loop exits
        r3 = make_tool_use_response(tool_id="toolu_03")
        mock_anthropic_client.messages.create.side_effect = [r1, r2, r3]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tool_manager=tool_manager)

        # Initial call + 2 loop rounds = 3 total; r3 is the final response (not executed)
        assert mock_anthropic_client.messages.create.call_count == 3
        assert tool_manager.execute_tool.call_count == 2

    def test_message_history_has_five_messages_after_two_rounds(self, generator, mock_anthropic_client):
        """After two tool rounds, the third API call must have 5 messages:
        user, assistant(round1), user(result1), assistant(round2), user(result2).
        """
        r1 = make_tool_use_response(tool_id="toolu_01")
        r2 = make_tool_use_response(tool_id="toolu_02")
        final = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [r1, r2, final]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="my query", tool_manager=tool_manager)

        third_call_kwargs = mock_anthropic_client.messages.create.call_args_list[2][1]
        messages = third_call_kwargs["messages"]
        assert len(messages) == 5
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[3]["role"] == "assistant"
        assert messages[4]["role"] == "user"

    def test_tool_result_ids_match_correct_round(self, generator, mock_anthropic_client):
        """Each tool_result block must carry the tool_use_id from its own round."""
        r1 = make_tool_use_response(tool_id="toolu_01")
        r2 = make_tool_use_response(tool_id="toolu_02")
        final = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [r1, r2, final]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tool_manager=tool_manager)

        third_call_kwargs = mock_anthropic_client.messages.create.call_args_list[2][1]
        messages = third_call_kwargs["messages"]
        # messages[2] is user(result1), messages[4] is user(result2)
        assert messages[2]["content"][0]["tool_use_id"] == "toolu_01"
        assert messages[4]["content"][0]["tool_use_id"] == "toolu_02"

    def test_tools_present_in_all_loop_api_calls(self, generator, mock_anthropic_client):
        """tools must be present in every API call when message history has tool blocks."""
        r1 = make_tool_use_response(tool_id="toolu_01")
        r2 = make_tool_use_response(tool_id="toolu_02")
        final = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [r1, r2, final]

        tools = [{"name": "search_course_content", "description": "Search", "input_schema": {}}]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        generator.generate_response(query="test", tools=tools, tool_manager=tool_manager)

        for i, api_call in enumerate(mock_anthropic_client.messages.create.call_args_list):
            assert "tools" in api_call[1], f"Call {i} missing 'tools' parameter"

    def test_tool_execution_error_does_not_raise(self, generator, mock_anthropic_client):
        """A tool execution exception must not propagate — it is fed back as error content."""
        r1 = make_tool_use_response(tool_id="toolu_01")
        final = make_direct_response("Handled gracefully")
        mock_anthropic_client.messages.create.side_effect = [r1, final]

        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = Exception("DB timeout")

        result = generator.generate_response(query="test", tool_manager=tool_manager)

        assert result == "Handled gracefully"
        assert mock_anthropic_client.messages.create.call_count == 2

    def test_tool_execution_error_content_sent_as_tool_result(self, generator, mock_anthropic_client):
        """The error message from a failed tool must appear in the tool_result content."""
        r1 = make_tool_use_response(tool_id="toolu_01")
        final = make_direct_response()
        mock_anthropic_client.messages.create.side_effect = [r1, final]

        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = Exception("DB timeout")
        generator.generate_response(query="test", tool_manager=tool_manager)

        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        tool_result_content = second_call_kwargs["messages"][2]["content"][0]["content"]
        assert "Tool execution error" in tool_result_content
        assert "DB timeout" in tool_result_content

    def test_state_does_not_leak_between_generate_response_calls(self, generator, mock_anthropic_client):
        """Round count must be local to each generate_response call, not stored on self."""
        # First call: two tool rounds
        r1 = make_tool_use_response(tool_id="toolu_01")
        r2 = make_tool_use_response(tool_id="toolu_02")
        final1 = make_direct_response("First call answer")
        # Second call: direct response, no tools
        final2 = make_direct_response("Second call answer")
        mock_anthropic_client.messages.create.side_effect = [r1, r2, final1, final2]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        result1 = generator.generate_response(query="first", tool_manager=tool_manager)
        result2 = generator.generate_response(query="second")

        assert result1 == "First call answer"
        assert result2 == "Second call answer"
        # 3 calls for first query + 1 for second
        assert mock_anthropic_client.messages.create.call_count == 4
