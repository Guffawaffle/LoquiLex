"""Remote model catalog search and provider abstraction.

Supports searching across multiple AI model providers with rate limiting and caching.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

import httpx
from loguru import logger


class ModelProvider(str, Enum):
    HUGGINGFACE = "huggingface"
    OPENAI = "openai" 
    LOCAL = "local"


class ModelTask(str, Enum):
    ASR = "asr"
    MT = "mt"
    TTS = "tts"
    EMBEDDING = "embedding"


@dataclass
class RemoteModel:
    """Remote model metadata."""
    id: str
    name: str
    provider: ModelProvider
    task: ModelTask
    language: Optional[str] = None
    languages: Optional[List[str]] = None
    size_bytes: Optional[int] = None
    description: Optional[str] = None
    downloads: Optional[int] = None
    license: Optional[str] = None
    updated_at: Optional[str] = None
    tags: Optional[List[str]] = None
    repo_url: Optional[str] = None
    model_class: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchFilters:
    """Search filters for model catalog."""
    task: Optional[ModelTask] = None
    language: Optional[str] = None
    provider: Optional[ModelProvider] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    query: Optional[str] = None


@dataclass
class SearchResult:
    """Search result with pagination."""
    models: List[RemoteModel]
    total: int
    page: int
    per_page: int
    has_next: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "models": [model.to_dict() for model in self.models],
            "total": self.total,
            "page": self.page,
            "per_page": self.per_page,
            "has_next": self.has_next
        }


class RateLimiter:
    """Simple rate limiter with sliding window."""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[float] = []
        
    async def acquire(self) -> bool:
        """Check if request is allowed within rate limit."""
        now = time.time()
        # Remove old requests outside window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.window_seconds]
        
        if len(self.requests) >= self.max_requests:
            return False
            
        self.requests.append(now)
        return True
    
    def get_reset_time(self) -> Optional[float]:
        """Get time until rate limit resets."""
        if not self.requests:
            return None
        oldest_request = min(self.requests)
        return oldest_request + self.window_seconds - time.time()


class HuggingFaceProvider:
    """Hugging Face model search provider."""
    
    def __init__(self):
        self.base_url = "https://huggingface.co/api"
        self.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
        
    async def search_models(
        self, 
        filters: SearchFilters, 
        page: int = 1, 
        per_page: int = 20
    ) -> SearchResult:
        """Search Hugging Face models."""
        if not await self.rate_limiter.acquire():
            raise Exception("Rate limit exceeded for Hugging Face API")
        
        # Build HF API parameters
        params: Dict[str, Union[str, int]] = {
            "limit": per_page,
            "full": "true",
            "config": "true"
        }
        
        if filters.query:
            params["search"] = filters.query
            
        if filters.task:
            # Map our task types to HF pipeline tags
            task_mapping = {
                ModelTask.ASR: "automatic-speech-recognition",
                ModelTask.MT: "translation",
                ModelTask.TTS: "text-to-speech",
                ModelTask.EMBEDDING: "feature-extraction"
            }
            mapped_task = task_mapping.get(filters.task)
            if mapped_task:
                params["pipeline_tag"] = mapped_task
            
        if filters.language:
            params["language"] = filters.language

        # Calculate offset for pagination
        offset = (page - 1) * per_page
        if offset > 0:
            params["skip"] = offset

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/models", params=params)
                response.raise_for_status()
                data = response.json()

            models = []
            for item in data:
                try:
                    model = self._parse_hf_model(item, filters)
                    if model:
                        models.append(model)
                except Exception as e:
                    logger.warning(f"Failed to parse HF model {item.get('id', 'unknown')}: {e}")
                    continue

            # HF API doesn't provide total count, so we estimate
            has_next = len(models) == per_page
            total = offset + len(models) + (per_page if has_next else 0)

            return SearchResult(
                models=models,
                total=total,
                page=page,
                per_page=per_page,
                has_next=has_next
            )

        except httpx.RequestError as e:
            logger.error(f"HuggingFace API request failed: {e}")
            raise Exception(f"Failed to search Hugging Face models: {e}")
        except Exception as e:
            logger.error(f"HuggingFace search error: {e}")
            raise

    def _parse_hf_model(self, item: Dict[str, Any], filters: SearchFilters) -> Optional[RemoteModel]:
        """Parse HuggingFace model data."""
        model_id = item.get("id", "")
        if not model_id:
            return None

        # Get pipeline tag and map to our task types
        pipeline_tag = item.get("pipeline_tag", "")
        task_mapping = {
            "automatic-speech-recognition": ModelTask.ASR,
            "translation": ModelTask.MT,
            "text-to-speech": ModelTask.TTS,
            "feature-extraction": ModelTask.EMBEDDING,
            "sentence-similarity": ModelTask.EMBEDDING
        }
        task = task_mapping.get(pipeline_tag)
        
        # Skip if task doesn't match our filter
        if filters.task and task != filters.task:
            return None
            
        if not task:
            # Default based on model name patterns
            model_lower = model_id.lower()
            if any(word in model_lower for word in ["whisper", "speech", "asr"]):
                task = ModelTask.ASR
            elif any(word in model_lower for word in ["translation", "translate", "nllb", "m2m"]):
                task = ModelTask.MT
            elif any(word in model_lower for word in ["tts", "voice", "speech-synthesis"]):
                task = ModelTask.TTS
            else:
                task = ModelTask.EMBEDDING

        # Extract model info
        name = model_id.split("/")[-1] if "/" in model_id else model_id
        description = item.get("description", "")
        downloads = item.get("downloads", 0)
        tags = item.get("tags", [])
        created_at = item.get("createdAt")
        
        # Extract language info
        languages = []
        if "language" in item:
            if isinstance(item["language"], list):
                languages = item["language"]
            elif isinstance(item["language"], str):
                languages = [item["language"]]
        
        # Extract from tags as well
        lang_tags = [tag for tag in tags if len(tag) == 2 or tag.startswith("lang:")]
        languages.extend(lang_tags)
        
        primary_language = languages[0] if languages else None
        
        # Get repo URL
        repo_url = f"https://huggingface.co/{model_id}"
        
        # Extract model class from config if available
        model_class = None
        config = item.get("config", {})
        if isinstance(config, dict):
            model_class = config.get("model_type") or config.get("architectures", [None])[0]

        return RemoteModel(
            id=model_id,
            name=name,
            provider=ModelProvider.HUGGINGFACE,
            task=task,
            language=primary_language,
            languages=languages if languages else None,
            description=description,
            downloads=downloads if downloads > 0 else None,
            tags=tags if tags else None,
            repo_url=repo_url,
            updated_at=created_at,
            model_class=model_class
        )

    async def get_model_details(self, model_id: str) -> Optional[RemoteModel]:
        """Get detailed model information."""
        if not await self.rate_limiter.acquire():
            raise Exception("Rate limit exceeded for Hugging Face API")
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/models/{model_id}")
                response.raise_for_status()
                data = response.json()

            return self._parse_hf_model(data, SearchFilters())
            
        except httpx.RequestError as e:
            logger.error(f"HuggingFace model details request failed: {e}")
            raise Exception(f"Failed to get model details: {e}")


class LocalProvider:
    """Local model provider using existing discovery."""
    
    def __init__(self):
        # Import here to avoid circular imports
        from .model_discovery import list_asr_models, list_mt_models
        self.list_asr_models = list_asr_models
        self.list_mt_models = list_mt_models
        
    async def search_models(
        self, 
        filters: SearchFilters, 
        page: int = 1, 
        per_page: int = 20
    ) -> SearchResult:
        """Search local models."""
        models = []
        
        # Get local ASR models
        if not filters.task or filters.task == ModelTask.ASR:
            asr_models = self.list_asr_models()
            for model_data in asr_models:
                models.append(RemoteModel(
                    id=model_data["id"],
                    name=model_data["name"],
                    provider=ModelProvider.LOCAL,
                    task=ModelTask.ASR,
                    language=model_data.get("language"),
                    size_bytes=model_data.get("size_bytes"),
                    description=f"Local {model_data.get('source', 'unknown')} model"
                ))
        
        # Get local MT models
        if not filters.task or filters.task == ModelTask.MT:
            mt_models = self.list_mt_models()
            for model_data in mt_models:
                models.append(RemoteModel(
                    id=model_data["id"],
                    name=model_data["name"],
                    provider=ModelProvider.LOCAL,
                    task=ModelTask.MT,
                    languages=model_data.get("langs"),
                    description="Local translation model"
                ))

        # Apply filters
        filtered_models = []
        for model in models:
            # Query filter
            if filters.query:
                query_lower = filters.query.lower()
                if not (query_lower in model.name.lower() or 
                       (model.description and query_lower in model.description.lower())):
                    continue
                    
            # Language filter
            if filters.language:
                if model.language != filters.language and \
                   not (model.languages and filters.language in model.languages):
                    continue
                    
            # Size filters
            if filters.min_size and (not model.size_bytes or model.size_bytes < filters.min_size):
                continue
            if filters.max_size and (model.size_bytes and model.size_bytes > filters.max_size):
                continue
                
            filtered_models.append(model)

        # Pagination
        total = len(filtered_models)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_models = filtered_models[start_idx:end_idx]
        
        return SearchResult(
            models=page_models,
            total=total,
            page=page,
            per_page=per_page,
            has_next=end_idx < total
        )

    async def get_model_details(self, model_id: str) -> Optional[RemoteModel]:
        """Get local model details."""
        # Search through local models to find the one with matching ID
        result = await self.search_models(SearchFilters(), page=1, per_page=1000)
        for model in result.models:
            if model.id == model_id:
                return model
        return None


class CatalogManager:
    """Manager for multiple model catalog providers."""
    
    def __init__(self):
        self.providers = {
            ModelProvider.HUGGINGFACE: HuggingFaceProvider(),
            ModelProvider.LOCAL: LocalProvider()
        }
        
    async def search_models(
        self, 
        filters: SearchFilters, 
        page: int = 1, 
        per_page: int = 20
    ) -> SearchResult:
        """Search across providers or specific provider."""
        if filters.provider:
            # Search specific provider
            provider = self.providers.get(filters.provider)
            if not provider:
                raise ValueError(f"Unknown provider: {filters.provider}")
            return await provider.search_models(filters, page, per_page)
        
        # Search all providers and combine results
        all_models = []
        tasks = []
        
        for provider_name, provider in self.providers.items():
            # Create provider-specific filters
            provider_filters = SearchFilters(
                task=filters.task,
                language=filters.language,
                provider=provider_name,
                min_size=filters.min_size,
                max_size=filters.max_size,
                query=filters.query
            )
            tasks.append(self._search_provider_safe(provider, provider_filters, 1, 100))
        
        # Wait for all providers to respond
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, SearchResult):
                all_models.extend(result.models)
            elif isinstance(result, Exception):
                logger.warning(f"Provider search failed: {result}")
        
        # Sort by relevance (downloads, then name)
        all_models.sort(key=lambda m: (-(m.downloads or 0), m.name))
        
        # Apply pagination to combined results
        total = len(all_models)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_models = all_models[start_idx:end_idx]
        
        return SearchResult(
            models=page_models,
            total=total,
            page=page,
            per_page=per_page,
            has_next=end_idx < total
        )

    async def _search_provider_safe(
        self, 
        provider: Union[HuggingFaceProvider, LocalProvider], 
        filters: SearchFilters, 
        page: int, 
        per_page: int
    ) -> SearchResult:
        """Search provider with error handling."""
        try:
            return await provider.search_models(filters, page, per_page)
        except Exception as e:
            logger.error(f"Provider {filters.provider} search failed: {e}")
            return SearchResult(models=[], total=0, page=page, per_page=per_page, has_next=False)

    async def get_model_details(self, model_id: str) -> Optional[RemoteModel]:
        """Get model details from appropriate provider."""
        # Try to determine provider from model ID
        if "/" in model_id and not model_id.startswith("/"):
            # Likely HuggingFace format (org/model)
            provider = self.providers[ModelProvider.HUGGINGFACE]
        else:
            # Try local first, then HuggingFace
            local_provider = self.providers[ModelProvider.LOCAL]
            model = await local_provider.get_model_details(model_id)
            if model:
                return model
            provider = self.providers[ModelProvider.HUGGINGFACE]
            
        return await provider.get_model_details(model_id)


# Global catalog manager instance
catalog_manager = CatalogManager()