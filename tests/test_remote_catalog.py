"""Tests for remote model catalog search functionality."""

import pytest
from unittest.mock import AsyncMock, patch

from loquilex.api.remote_catalog import (
    CatalogManager, 
    SearchFilters, 
    ModelProvider, 
    ModelTask, 
    RemoteModel,
    SearchResult,
    RateLimiter
)


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_init(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.max_requests == 5
        assert limiter.window_seconds == 60
        assert limiter.requests == []
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_under_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # Should allow first 3 requests
        assert await limiter.acquire()
        assert await limiter.acquire()
        assert await limiter.acquire()
        
        # Should deny 4th request
        assert not await limiter.acquire()
    
    def test_rate_limiter_reset_time(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        
        # No requests yet
        assert limiter.get_reset_time() is None
        
        # Add a request
        limiter.requests = [100.0]  # Mock timestamp
        reset_time = limiter.get_reset_time()
        assert reset_time is not None


class TestSearchFilters:
    """Test search filter functionality."""
    
    def test_search_filters_init(self):
        filters = SearchFilters()
        assert filters.task is None
        assert filters.language is None
        assert filters.provider is None
        assert filters.query is None
    
    def test_search_filters_with_values(self):
        filters = SearchFilters(
            task=ModelTask.ASR,
            language="en",
            provider=ModelProvider.HUGGINGFACE,
            query="whisper"
        )
        assert filters.task == ModelTask.ASR
        assert filters.language == "en"
        assert filters.provider == ModelProvider.HUGGINGFACE
        assert filters.query == "whisper"


class TestRemoteModel:
    """Test remote model data structure."""
    
    def test_remote_model_init(self):
        model = RemoteModel(
            id="test/model",
            name="Test Model",
            provider=ModelProvider.HUGGINGFACE,
            task=ModelTask.ASR
        )
        assert model.id == "test/model"
        assert model.name == "Test Model"
        assert model.provider == ModelProvider.HUGGINGFACE
        assert model.task == ModelTask.ASR
    
    def test_remote_model_to_dict(self):
        model = RemoteModel(
            id="test/model",
            name="Test Model",
            provider=ModelProvider.HUGGINGFACE,
            task=ModelTask.ASR,
            description="A test model",
            downloads=1000
        )
        data = model.to_dict()
        assert data["id"] == "test/model"
        assert data["name"] == "Test Model"
        assert data["description"] == "A test model"
        assert data["downloads"] == 1000


class TestSearchResult:
    """Test search result structure."""
    
    def test_search_result_to_dict(self):
        model = RemoteModel(
            id="test/model",
            name="Test Model", 
            provider=ModelProvider.LOCAL,
            task=ModelTask.ASR
        )
        result = SearchResult(
            models=[model],
            total=1,
            page=1,
            per_page=20,
            has_next=False
        )
        
        data = result.to_dict()
        assert len(data["models"]) == 1
        assert data["models"][0]["id"] == "test/model"
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["has_next"] is False


@pytest.mark.asyncio
class TestLocalProvider:
    """Test local model provider."""
    
    @patch('loquilex.api.model_discovery.list_asr_models')
    @patch('loquilex.api.model_discovery.list_mt_models')
    async def test_search_local_models(self, mock_mt_models, mock_asr_models):
        # Mock the model discovery functions
        mock_asr_models.return_value = [
            {"id": "tiny.en", "name": "tiny.en", "source": "hf", "language": "en", "size_bytes": 1000000}
        ]
        mock_mt_models.return_value = [
            {"id": "nllb-200", "name": "nllb-200", "langs": ["en", "zh"]}
        ]
        
        from loquilex.api.remote_catalog import LocalProvider
        provider = LocalProvider()
        
        # Test search without filters
        result = await provider.search_models(SearchFilters(), page=1, per_page=20)
        
        assert len(result.models) == 2
        assert result.models[0].provider == ModelProvider.LOCAL
        assert result.models[1].provider == ModelProvider.LOCAL
        
        # Test ASR filter
        asr_filter = SearchFilters(task=ModelTask.ASR)
        result = await provider.search_models(asr_filter, page=1, per_page=20)
        
        assert len(result.models) == 1
        assert result.models[0].task == ModelTask.ASR
        
        # Test MT filter  
        mt_filter = SearchFilters(task=ModelTask.MT)
        result = await provider.search_models(mt_filter, page=1, per_page=20)
        
        assert len(result.models) == 1
        assert result.models[0].task == ModelTask.MT


@pytest.mark.asyncio  
class TestCatalogManager:
    """Test catalog manager integration."""
    
    async def test_catalog_manager_init(self):
        manager = CatalogManager()
        assert ModelProvider.HUGGINGFACE in manager.providers
        assert ModelProvider.LOCAL in manager.providers
    
    @patch('loquilex.api.remote_catalog.LocalProvider.search_models')
    async def test_search_with_provider_filter(self, mock_local_search):
        # Mock local provider response
        mock_result = SearchResult(
            models=[RemoteModel(
                id="local_model", 
                name="Local Model", 
                provider=ModelProvider.LOCAL,
                task=ModelTask.ASR
            )],
            total=1,
            page=1,
            per_page=20,
            has_next=False
        )
        mock_local_search.return_value = mock_result
        
        manager = CatalogManager()
        filters = SearchFilters(provider=ModelProvider.LOCAL)
        
        result = await manager.search_models(filters, page=1, per_page=20)
        
        assert len(result.models) == 1
        assert result.models[0].provider == ModelProvider.LOCAL
        mock_local_search.assert_called_once()
    
    async def test_search_with_invalid_provider(self):
        manager = CatalogManager()
        
        # This should raise ValueError for invalid provider
        with pytest.raises(ValueError, match="Unknown provider"):
            filters = SearchFilters(provider="invalid_provider")  # type: ignore
            await manager.search_models(filters)


# Integration test with actual API endpoints
class TestSearchAPI:
    """Test the FastAPI search endpoints."""
    
    def test_model_task_enum_values(self):
        """Test that ModelTask enum has expected values."""
        assert ModelTask.ASR == "asr"
        assert ModelTask.MT == "mt" 
        assert ModelTask.TTS == "tts"
        assert ModelTask.EMBEDDING == "embedding"
    
    def test_model_provider_enum_values(self):
        """Test that ModelProvider enum has expected values."""
        assert ModelProvider.HUGGINGFACE == "huggingface"
        assert ModelProvider.OPENAI == "openai"
        assert ModelProvider.LOCAL == "local"