"""
Integration tests for RAGSystem.query() in rag_system.py.

These tests mock AIGenerator and VectorStore to verify the full pipeline:
- Tools are wired up and passed to the generator
- Sources are collected and returned, then reset
- Session history is retrieved and forwarded
- Exceptions propagate (not silently swallowed)
"""
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from rag_system import RAGSystem


@pytest.fixture
def test_config():
    """Minimal config object for RAGSystem instantiation."""
    return SimpleNamespace(
        ANTHROPIC_API_KEY="test-key",
        ANTHROPIC_MODEL="test-model",
        EMBEDDING_MODEL="all-MiniLM-L6-v2",
        CHUNK_SIZE=800,
        CHUNK_OVERLAP=100,
        MAX_RESULTS=5,
        MAX_HISTORY=2,
        CHROMA_PATH="./test_chroma_db",
    )


@pytest.fixture
def rag_system(test_config):
    """RAGSystem with VectorStore and AIGenerator patched out."""
    with (
        patch("rag_system.VectorStore") as MockVS,
        patch("rag_system.AIGenerator") as MockAI,
    ):
        rag = RAGSystem(test_config)
        # Expose the mocks for assertion in tests
        rag._mock_vector_store = MockVS.return_value
        rag._mock_ai_generator = MockAI.return_value
        yield rag


class TestRAGSystemQueryReturnShape:

    def test_query_returns_tuple(self, rag_system):
        """query() must return a (str, list) tuple."""
        rag_system._mock_ai_generator.generate_response.return_value = "answer"
        result = rag_system.query("What is covered in Lesson 1?")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], list)

    def test_query_returns_generator_answer(self, rag_system):
        """result[0] must be exactly what generate_response() returned."""
        rag_system._mock_ai_generator.generate_response.return_value = "The answer is 42."
        result = rag_system.query("some question")
        assert result[0] == "The answer is 42."


class TestRAGSystemToolWiring:

    def test_generate_response_receives_tools(self, rag_system):
        """generate_response() must be called with a non-empty tools list."""
        rag_system._mock_ai_generator.generate_response.return_value = "ok"
        rag_system.query("What does lesson 2 cover?")

        call_kwargs = rag_system._mock_ai_generator.generate_response.call_args[1]
        assert "tools" in call_kwargs
        assert isinstance(call_kwargs["tools"], list)
        assert len(call_kwargs["tools"]) > 0

    def test_generate_response_receives_tool_manager(self, rag_system):
        """generate_response() must be called with the ToolManager instance."""
        rag_system._mock_ai_generator.generate_response.return_value = "ok"
        rag_system.query("course question")

        call_kwargs = rag_system._mock_ai_generator.generate_response.call_args[1]
        assert "tool_manager" in call_kwargs
        assert call_kwargs["tool_manager"] is rag_system.tool_manager

    def test_query_prompt_wraps_user_question(self, rag_system):
        """The query forwarded to generate_response must wrap the user's question."""
        rag_system._mock_ai_generator.generate_response.return_value = "ok"
        rag_system.query("What is covered in Lesson 1?")

        call_kwargs = rag_system._mock_ai_generator.generate_response.call_args[1]
        forwarded_query = call_kwargs.get("query", "")
        assert "What is covered in Lesson 1?" in forwarded_query


class TestRAGSystemSources:

    def test_sources_returned_from_tool_manager(self, rag_system):
        """result[1] must be the sources list returned by tool_manager.get_last_sources()."""
        rag_system._mock_ai_generator.generate_response.return_value = "answer"
        # Patch get_last_sources on the real tool_manager inside rag_system
        rag_system.tool_manager.get_last_sources = MagicMock(return_value=["src1", "src2"])
        rag_system.tool_manager.reset_sources = MagicMock()

        result = rag_system.query("content question")
        assert result[1] == ["src1", "src2"]

    def test_sources_reset_after_query(self, rag_system):
        """reset_sources() must be called exactly once after every query."""
        rag_system._mock_ai_generator.generate_response.return_value = "answer"
        rag_system.tool_manager.get_last_sources = MagicMock(return_value=[])
        rag_system.tool_manager.reset_sources = MagicMock()

        rag_system.query("question")
        rag_system.tool_manager.reset_sources.assert_called_once()

    def test_sources_reset_even_if_no_sources(self, rag_system):
        """reset_sources() must still be called when no sources were collected."""
        rag_system._mock_ai_generator.generate_response.return_value = "answer"
        rag_system.tool_manager.get_last_sources = MagicMock(return_value=[])
        rag_system.tool_manager.reset_sources = MagicMock()

        rag_system.query("general question")
        rag_system.tool_manager.reset_sources.assert_called_once()


class TestRAGSystemSessionHistory:

    def test_no_history_when_no_session_id(self, rag_system):
        """Without a session_id, generate_response must receive conversation_history=None."""
        rag_system._mock_ai_generator.generate_response.return_value = "answer"
        rag_system.query("question")

        call_kwargs = rag_system._mock_ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") is None

    def test_history_passed_when_session_exists(self, rag_system):
        """With an active session that has history, conversation_history must be non-None."""
        rag_system._mock_ai_generator.generate_response.return_value = "answer"

        # Create a session and add an exchange so history exists
        session_id = rag_system.session_manager.create_session()
        rag_system.session_manager.add_exchange(session_id, "prev question", "prev answer")

        rag_system.query("follow-up question", session_id=session_id)

        call_kwargs = rag_system._mock_ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") is not None

    def test_history_updated_after_query(self, rag_system):
        """After a query with a session_id, the session must contain the new exchange."""
        rag_system._mock_ai_generator.generate_response.return_value = "the response"

        session_id = rag_system.session_manager.create_session()
        rag_system.query("user question", session_id=session_id)

        history = rag_system.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "user question" in history
        assert "the response" in history


class TestRAGSystemErrorHandling:

    def test_exception_from_generator_propagates(self, rag_system):
        """If generate_response() raises, the exception must not be silently swallowed."""
        rag_system._mock_ai_generator.generate_response.side_effect = Exception("API failure")

        with pytest.raises(Exception, match="API failure"):
            rag_system.query("content question")

    def test_exception_type_is_preserved(self, rag_system):
        """The original exception type must propagate unchanged."""
        rag_system._mock_ai_generator.generate_response.side_effect = ValueError("bad value")

        with pytest.raises(ValueError):
            rag_system.query("question")
