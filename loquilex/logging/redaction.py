"""Sensitive data redaction for structured logging."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Union


class DataRedactor:
    """Redact sensitive information from log data."""
    
    def __init__(self, custom_patterns: Optional[List[Pattern[str]]] = None) -> None:
        """Initialize redactor with standard and custom patterns.
        
        Args:
            custom_patterns: Additional regex patterns to redact
        """
        # Standard sensitive data patterns
        self.patterns = [
            # File paths (keep only filename) - improved to handle Windows paths
            re.compile(r'([A-Za-z]:\\|/)[^/\\\s]*[/\\]([^/\\\s]+\.(py|json|yaml|yml|txt|log|bin|ckpt|pt|pth|safetensors))'),
            
            # Model paths and cache directories  
            re.compile(r'(/.+/)?(\.cache|models|checkpoints)/[^\s]+'),
            
            # Tokens and API keys (common patterns)
            re.compile(r'(token|key|secret|password|api_key|credential)["\']?\s*[=:]\s*["\']?[a-zA-Z0-9_-]{8,}["\']?', re.IGNORECASE),
            
            # User home directories
            re.compile(r'/home/[^/\s]+'),
            re.compile(r'/Users/[^/\s]+'),
            re.compile(r'C:\\Users\\[^\\s]+'),
        ]
        
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        
        # Sensitive field names to redact entirely
        self.sensitive_fields = {
            'password', 'token', 'secret', 'key', 'auth', 'credential',
            'user_data', 'personal_info', 'email', 'phone', 'address',
            'api_key', 'access_token', 'refresh_token', 'auth_token'
        }
    
    def redact_string(self, text: str) -> str:
        """Redact sensitive information from a string.
        
        Args:
            text: Input text to redact
            
        Returns:
            Redacted text with sensitive data replaced
        """
        result = text
        
        for pattern in self.patterns:
            if pattern.groups >= 2:
                # Keep certain parts (like filenames)
                result = pattern.sub(r'[REDACTED]/\2', result)
            else:
                result = pattern.sub('[REDACTED]', result)
        
        return result
    
    def redact_path(self, path: Union[str, Path]) -> str:
        """Redact file paths while preserving filename.
        
        Args:
            path: File path to redact
            
        Returns:
            Redacted path with directory structure hidden
        """
        path_str = str(path)
        path_obj = Path(path_str)
        
        # Keep only filename and indicate it was redacted
        return f"[REDACTED]/{path_obj.name}"
    
    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive data from dictionary.
        
        Args:
            data: Dictionary to redact
            
        Returns:
            Dictionary with sensitive data redacted
        """
        result = {}
        
        for key, value in data.items():
            # Check if field name itself is sensitive
            if key.lower() in self.sensitive_fields:
                result[key] = "[REDACTED]"
                continue
            
            # Recursively process nested data
            if isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.redact_dict(item) if isinstance(item, dict)
                    else self.redact_string(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            elif isinstance(value, str):
                result[key] = self.redact_string(value)
            elif isinstance(value, (Path, )):
                result[key] = self.redact_path(value)
            else:
                result[key] = value
        
        return result
    
    def add_pattern(self, pattern: Union[str, Pattern[str]]) -> None:
        """Add custom redaction pattern.
        
        Args:
            pattern: Regex pattern (string or compiled) to add
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        self.patterns.append(pattern)
    
    def add_sensitive_field(self, field_name: str) -> None:
        """Add field name to redact entirely.
        
        Args:
            field_name: Field name to redact (case-insensitive)
        """
        self.sensitive_fields.add(field_name.lower())