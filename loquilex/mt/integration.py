"""MT integration for WebSocket API and session management."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Awaitable

from .service import MTService
from .core.util import normalize_lang


class MTIntegration:
    """MT integration for WebSocket sessions."""
    
    def __init__(self, session_id: str, mt_enabled: bool = True, dest_lang: str = "zh-Hans"):
        self.session_id = session_id
        self.mt_enabled = mt_enabled
        self.dest_lang = dest_lang
        self._mt_service: Optional[MTService] = None
        self._broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
        
        # Initialize MT service if enabled
        if self.mt_enabled:
            try:
                self._mt_service = MTService()
                if not self._mt_service.is_available():
                    self._mt_service = None
                    self.mt_enabled = False
            except Exception:
                self._mt_service = None
                self.mt_enabled = False
    
    def set_broadcast_fn(self, broadcast_fn: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        """Set the broadcast function for emitting events."""
        self._broadcast_fn = broadcast_fn
    
    async def translate_and_emit(
        self, 
        text: str, 
        segment_id: str, 
        is_final: bool = True,
        src_lang: str = "en"
    ) -> None:
        """Translate text and emit MT event."""
        if not self.mt_enabled or not self._mt_service or not self._broadcast_fn:
            return
        
        if not text.strip():
            return
        
        try:
            # Normalize destination language
            tgt_lang = normalize_lang(self.dest_lang)
            
            # Perform translation
            result = self._mt_service.translate_text(
                text=text,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                quality="realtime"
            )
            
            # Emit MT event
            event_type = "mt.final" if is_final else "mt.partial"
            event = {
                "type": event_type,
                "stream_id": self.session_id,
                "segment_id": segment_id,
                "text": result.text,
                "src_text": text,
                "src_lang": result.src_lang,
                "tgt_lang": result.tgt_lang,
                "provider": result.provider,
                "quality": result.quality
            }
            
            await self._broadcast_fn(self.session_id, event)
            
        except Exception as e:
            # Emit error event on translation failure
            error_event = {
                "type": "mt.error",
                "stream_id": self.session_id,
                "segment_id": segment_id,
                "error": str(e),
                "src_text": text
            }
            
            if self._broadcast_fn is not None:
                await self._broadcast_fn(self.session_id, error_event)
    
    async def translate_chunked_and_emit(
        self,
        chunks: list[str],
        segment_ids: list[str],
        src_lang: str = "en"
    ) -> None:
        """Translate multiple chunks and emit MT events."""
        if not self.mt_enabled or not self._mt_service or not self._broadcast_fn:
            return
        
        if len(chunks) != len(segment_ids):
            raise ValueError("chunks and segment_ids must have same length")
        
        try:
            # Normalize destination language  
            tgt_lang = normalize_lang(self.dest_lang)
            
            # Perform chunked translation
            results = list(self._mt_service.translate_chunked(
                chunks=chunks,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                quality="realtime"
            ))
            
            # Emit events for each result
            for i, result in enumerate(results):
                if i < len(segment_ids):
                    event = {
                        "type": "mt.final",
                        "stream_id": self.session_id,
                        "segment_id": segment_ids[i],
                        "text": result.text,
                        "src_text": chunks[i],
                        "src_lang": result.src_lang,
                        "tgt_lang": result.tgt_lang,
                        "provider": result.provider,
                        "quality": result.quality
                    }
                    
                    await self._broadcast_fn(self.session_id, event)
                    
        except Exception as e:
            # Emit error event
            error_event = {
                "type": "mt.error",
                "stream_id": self.session_id,
                "error": str(e),
                "src_chunks": chunks
            }
            
            if self._broadcast_fn is not None:
                await self._broadcast_fn(self.session_id, error_event)
    
    def get_status(self) -> Dict[str, Any]:
        """Get MT integration status."""
        status = {
            "enabled": self.mt_enabled,
            "dest_lang": self.dest_lang,
            "provider": None,
            "available": False
        }
        
        if self._mt_service:
            status["provider"] = self._mt_service.get_provider_name()
            status["available"] = self._mt_service.is_available()
            status["capabilities"] = self._mt_service.get_capabilities()
        
        return status


def create_mt_integration(session_config) -> MTIntegration:
    """Create MT integration from session config."""
    return MTIntegration(
        session_id="",  # Will be set later
        mt_enabled=getattr(session_config, 'mt_enabled', False),
        dest_lang=getattr(session_config, 'dest_lang', 'zh-Hans')
    )