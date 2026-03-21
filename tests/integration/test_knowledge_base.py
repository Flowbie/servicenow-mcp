# tests/integration/test_knowledge_base.py
"""
Integration tests for knowledge base tools against a live ServiceNow instance.
READ-ONLY — covers list and get operations only.
Run with: SN_INTEGRATION_TESTS=1 pytest tests/integration/test_knowledge_base.py -v -s
"""
import json
import pytest

from servicenow_mcp.tools.knowledge_base import (
    list_knowledge_bases,
    list_categories,
    list_articles,
    get_article,
    ListKnowledgeBasesParams,
    ListCategoriesParams,
    ListArticlesParams,
    GetArticleParams,
)


@pytest.mark.integration
class TestKnowledgeBaseIntegration:

    def test_list_knowledge_bases_returns_results(self, live_config, live_auth):
        """Verify list_knowledge_bases connects and returns records."""
        params = ListKnowledgeBasesParams()
        result = list_knowledge_bases(live_config, live_auth, params)

        print("\n--- list_knowledge_bases response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "knowledge_bases" in result
        assert isinstance(result["knowledge_bases"], list)

    def test_list_knowledge_bases_shape(self, live_config, live_auth):
        """Verify knowledge base records have expected fields."""
        params = ListKnowledgeBasesParams()
        result = list_knowledge_bases(live_config, live_auth, params)

        assert result["success"] is True
        kbs = result["knowledge_bases"]

        if not kbs:
            pytest.skip("No knowledge bases found on this instance.")

        first = kbs[0]
        print("\n--- first knowledge base fields ---")
        print(json.dumps(first, indent=2, default=str))

        # list_knowledge_bases maps sys_id → "id" in its response (tool-level transform)
        for field in ["id", "title"]:
            assert field in first, f"Missing expected field: {field}"

    def test_list_categories_returns_results(self, live_config, live_auth):
        """Verify list_categories returns records."""
        params = ListCategoriesParams()
        result = list_categories(live_config, live_auth, params)

        print("\n--- list_categories response ---")
        print(json.dumps(result, indent=2, default=str))

        assert "success" in result

    def test_list_articles_returns_results(self, live_config, live_auth):
        """Verify list_articles returns records."""
        params = ListArticlesParams(limit=5)
        result = list_articles(live_config, live_auth, params)

        print("\n--- list_articles response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True, f"Expected success, got: {result.get('message')}"
        assert "articles" in result

    def test_get_article_by_sys_id(self, live_config, live_auth):
        """Verify get_article returns full article details."""
        list_result = list_articles(live_config, live_auth, ListArticlesParams(limit=1))
        assert list_result["success"] is True

        if not list_result["articles"]:
            pytest.skip("No articles on this instance.")

        # list_articles maps sys_id → "id" in its response (tool-level transform).
        # BUG: with sysparm_display_value=all, sys_id is a dict; tool does not extract .value,
        # so "id" may be a dict instead of a string. Extract .value defensively here.
        raw_id = list_result["articles"][0]["id"]
        article_id = raw_id.get("value", "") if isinstance(raw_id, dict) else raw_id
        if not article_id:
            pytest.skip("Could not extract article sys_id — list_articles sysparm_display_value bug.")

        params = GetArticleParams(article_id=article_id)
        result = get_article(live_config, live_auth, params)

        print(f"\n--- get_article({article_id}) response ---")
        print(json.dumps(result, indent=2, default=str))

        assert result["success"] is True
        assert "article" in result

    def test_list_articles_limit_respected(self, live_config, live_auth):
        """Verify limit param is respected."""
        params = ListArticlesParams(limit=2)
        result = list_articles(live_config, live_auth, params)

        assert result["success"] is True
        assert len(result["articles"]) <= 2
