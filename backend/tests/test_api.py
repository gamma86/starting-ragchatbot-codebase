import pytest
from unittest.mock import MagicMock


class TestQueryEndpoint:
    def test_query_with_session_id(self, client, mock_rag_system):
        response = client.post(
            "/api/query",
            json={"query": "What is Python?", "session_id": "existing-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"
        assert data["sources"] == ["source1", "source2"]
        assert data["session_id"] == "existing-session"
        mock_rag_system.query.assert_called_once_with("What is Python?", "existing-session")

    def test_query_without_session_id_creates_session(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "Tell me about lists"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("Tell me about lists", "test-session-123")

    def test_query_returns_empty_sources(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer with no sources", [])
        response = client.post("/api/query", json={"query": "General question"})
        assert response.status_code == 200
        assert response.json()["sources"] == []

    def test_query_rag_error_returns_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("Vector store unavailable")
        response = client.post("/api/query", json={"query": "Some query"})
        assert response.status_code == 500
        assert "Vector store unavailable" in response.json()["detail"]

    def test_query_missing_body_returns_422(self, client):
        response = client.post("/api/query", json={})
        assert response.status_code == 422

    def test_query_response_shape(self, client):
        response = client.post("/api/query", json={"query": "test"})
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"answer", "sources", "session_id"}
        assert isinstance(data["sources"], list)


class TestCoursesEndpoint:
    def test_get_courses_returns_stats(self, client, mock_rag_system):
        response = client.get("/api/courses")
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 2
        assert data["course_titles"] == ["Course A", "Course B"]

    def test_get_courses_empty(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        response = client.get("/api/courses")
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_courses_analytics_error_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = Exception("DB error")
        response = client.get("/api/courses")
        assert response.status_code == 500
        assert "DB error" in response.json()["detail"]

    def test_get_courses_response_shape(self, client):
        response = client.get("/api/courses")
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"total_courses", "course_titles"}
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)


class TestDeleteSessionEndpoint:
    def test_delete_session_clears_and_returns_ok(self, client, mock_rag_system):
        response = client.delete("/api/session/abc-123")
        assert response.status_code == 200
        assert response.json() == {"status": "cleared"}
        mock_rag_system.session_manager.clear_session.assert_called_once_with("abc-123")

    def test_delete_session_passes_correct_id(self, client, mock_rag_system):
        session_id = "user-session-xyz"
        client.delete(f"/api/session/{session_id}")
        mock_rag_system.session_manager.clear_session.assert_called_once_with(session_id)
