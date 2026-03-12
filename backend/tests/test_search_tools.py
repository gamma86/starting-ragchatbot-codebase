"""
Tests for CourseSearchTool.execute() in search_tools.py.

These tests use a mocked VectorStore to verify:
- Correct parameters are forwarded to store.search()
- Results are formatted correctly
- Edge cases (empty results, errors) are handled
- Sources (last_sources) are populated correctly
"""
import pytest
from unittest.mock import MagicMock, patch

from vector_store import SearchResults
from search_tools import CourseSearchTool


def make_search_results(docs, metadatas, distances=None, error=None):
    """Helper to build SearchResults objects for tests."""
    if error:
        return SearchResults.empty(error)
    return SearchResults(
        documents=docs,
        metadata=metadatas,
        distances=distances or [0.1] * len(docs),
        error=None,
    )


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_lesson_link.return_value = None
    return store


@pytest.fixture
def tool(mock_store):
    return CourseSearchTool(mock_store)


class TestCourseSearchToolExecute:

    # ── parameter forwarding ────────────────────────────────────────────────

    def test_execute_passes_query_to_store(self, tool, mock_store):
        """store.search() must be called with the exact query text."""
        mock_store.search.return_value = make_search_results(
            ["content"], [{"course_title": "Py", "lesson_number": 1}]
        )
        tool.execute(query="test query")
        mock_store.search.assert_called_once_with(
            query="test query", course_name=None, lesson_number=None
        )

    def test_execute_passes_course_name_filter(self, tool, mock_store):
        """course_name kwarg must be forwarded to store.search()."""
        mock_store.search.return_value = make_search_results(
            ["content"], [{"course_title": "Python", "lesson_number": 1}]
        )
        tool.execute(query="test", course_name="Python")
        mock_store.search.assert_called_once_with(
            query="test", course_name="Python", lesson_number=None
        )

    def test_execute_passes_lesson_number_filter(self, tool, mock_store):
        """lesson_number kwarg must be forwarded to store.search()."""
        mock_store.search.return_value = make_search_results(
            ["content"], [{"course_title": "Py", "lesson_number": 2}]
        )
        tool.execute(query="test", lesson_number=2)
        mock_store.search.assert_called_once_with(
            query="test", course_name=None, lesson_number=2
        )

    # ── result formatting ───────────────────────────────────────────────────

    def test_execute_returns_formatted_results(self, tool, mock_store):
        """Output must contain the course/lesson header and document text."""
        mock_store.search.return_value = make_search_results(
            ["lesson content here"],
            [{"course_title": "Python Basics", "lesson_number": 1}],
        )
        result = tool.execute(query="test")
        assert "[Python Basics - Lesson 1]" in result
        assert "lesson content here" in result

    def test_execute_formats_multiple_results(self, tool, mock_store):
        """Multiple docs should be joined with double newlines."""
        mock_store.search.return_value = make_search_results(
            ["doc one", "doc two"],
            [
                {"course_title": "CourseA", "lesson_number": 1},
                {"course_title": "CourseB", "lesson_number": 2},
            ],
        )
        result = tool.execute(query="test")
        assert "[CourseA - Lesson 1]" in result
        assert "[CourseB - Lesson 2]" in result
        assert "doc one" in result
        assert "doc two" in result

    def test_execute_formats_result_without_lesson_number(self, tool, mock_store):
        """Results without a lesson_number should not include '- Lesson' in header."""
        mock_store.search.return_value = make_search_results(
            ["content"], [{"course_title": "MyCourse"}]
        )
        result = tool.execute(query="test")
        assert "[MyCourse]" in result
        assert "Lesson" not in result

    # ── edge cases ──────────────────────────────────────────────────────────

    def test_execute_returns_error_string_on_store_error(self, tool, mock_store):
        """If SearchResults has an error, execute() returns that error string directly."""
        mock_store.search.return_value = make_search_results(
            [], [], error="Search error: DB down"
        )
        result = tool.execute(query="test")
        assert result == "Search error: DB down"

    def test_execute_returns_no_results_message_when_empty(self, tool, mock_store):
        """Empty SearchResults (no error) should return a 'no results' message."""
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        result = tool.execute(query="test")
        assert "No relevant content found" in result

    def test_execute_no_results_message_includes_course_name(self, tool, mock_store):
        """Empty results with course_name filter should mention the course in the message."""
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        result = tool.execute(query="test", course_name="Python")
        assert "Python" in result

    def test_execute_no_results_message_includes_lesson_number(self, tool, mock_store):
        """Empty results with lesson_number filter should mention the lesson in the message."""
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        result = tool.execute(query="test", lesson_number=3)
        assert "3" in result

    # ── sources (last_sources) tracking ────────────────────────────────────

    def test_execute_populates_last_sources_without_link(self, tool, mock_store):
        """last_sources should be populated with plain text when there is no lesson link."""
        mock_store.get_lesson_link.return_value = None
        mock_store.search.return_value = make_search_results(
            ["content"], [{"course_title": "Py Course", "lesson_number": 1}]
        )
        tool.execute(query="test")
        assert tool.last_sources == ["Py Course - Lesson 1"]

    def test_execute_populates_last_sources_with_link(self, tool, mock_store):
        """last_sources should contain an HTML anchor tag when a lesson link is available."""
        mock_store.get_lesson_link.return_value = "http://example.com/lesson1"
        mock_store.search.return_value = make_search_results(
            ["content"], [{"course_title": "Py Course", "lesson_number": 1}]
        )
        tool.execute(query="test")
        assert len(tool.last_sources) == 1
        src = tool.last_sources[0]
        assert '<a href="http://example.com/lesson1"' in src
        assert "Py Course - Lesson 1" in src

    def test_last_sources_not_updated_on_empty_result(self, tool, mock_store):
        """last_sources should remain unchanged (not cleared) when results are empty."""
        tool.last_sources = ["previous source"]
        mock_store.search.return_value = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        tool.execute(query="test")
        # _format_results is never called for empty results, so last_sources stays
        assert tool.last_sources == ["previous source"]

    def test_last_sources_not_updated_on_error(self, tool, mock_store):
        """last_sources should remain unchanged when the store returns an error."""
        tool.last_sources = ["previous source"]
        mock_store.search.return_value = make_search_results([], [], error="DB error")
        tool.execute(query="test")
        assert tool.last_sources == ["previous source"]
