# Provider Abstraction Specification

## Overview

This specification defines the provider abstraction layer for managing tokens and credentials required by various ML model providers, with special attention to offline-first operation.

## Core Requirements

### Provider Types

1. **HuggingFace (HF)**: Primary model provider requiring authentication tokens
   - Models: ASR (Whisper), MT (NLLB, M2M100)
   - Token required for: private models, rate limiting, enhanced access
   - Offline behavior: Uses cached models when HF_HUB_OFFLINE=1

### Token Management

1. **Storage**: Tokens stored securely in backend configuration
   - Environment variables: `LX_HF_TOKEN`
   - Configuration file: `~/.loquilex/providers.json` (optional)
   - UI input: Secure text field with validation

2. **Security**: 
   - No tokens in localStorage/client-side storage
   - Backend validates tokens before storing
   - Tokens encrypted at rest (future enhancement)

### Offline Mode

1. **Configuration**: 
   - UI toggle: "Enable Offline Mode"
   - Backend setting: `backend.offline` flag
   - Environment override: `LX_OFFLINE=1`

2. **Behavior**:
   - When offline: Skip all network requests, use only cached models
   - When online: Allow model downloads, token validation
   - Graceful degradation: Fall back to offline if network unavailable

## API Endpoints

### Provider Configuration
- `GET /api/providers/config` - Get current provider configuration status
- `POST /api/providers/hf/token` - Set/update HuggingFace token
- `DELETE /api/providers/hf/token` - Remove HuggingFace token
- `POST /api/providers/offline` - Toggle offline mode

### Health & Status
- `GET /api/health` - Include offline status and provider configuration

## Implementation Notes

1. **Backward Compatibility**: Respect existing environment variables
2. **Progressive Enhancement**: UI works without tokens, shows limitations
3. **Error Handling**: Clear messaging for token validation failures
4. **Testing**: Mock providers for offline development and CI