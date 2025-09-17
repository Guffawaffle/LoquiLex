"""Tests for structured logging and performance metrics."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from loquilex.logging import (
    StructuredLogger, 
    create_logger,
    PerformanceMetrics,
    DataRedactor,
)


class TestDataRedactor:
    """Test sensitive data redaction."""
    
    def test_redact_file_paths(self):
        """Test file path redaction preserves filename."""
        redactor = DataRedactor()
        
        # Test various path formats that should preserve filenames
        test_cases = [
            ("/home/user/project/model.py", "model.py"),
            ("C:\\Users\\jane\\Documents\\secret.txt", "secret.txt"),
        ]
        
        for path, expected_filename in test_cases:
            result = redactor.redact_string(path)
            assert "[REDACTED]" in result
            # Should preserve filename for supported file types
            if any(path.endswith(ext) for ext in ['.py', '.txt', '.json', '.yaml', '.log']):
                assert expected_filename in result
        
        # Test cache directories (these get fully redacted for security)
        cache_path = "/Users/john/.cache/huggingface/models/bert.json"
        result = redactor.redact_string(cache_path)
        assert "[REDACTED]" in result
    
    def test_redact_sensitive_fields(self):
        """Test sensitive field redaction."""
        redactor = DataRedactor()
        
        data = {
            "token": "abc123def456",
            "password": "secret123",
            "model_path": "/home/user/models/bert.bin",
            "safe_field": "this is safe",
        }
        
        result = redactor.redact_dict(data)
        
        assert result["token"] == "[REDACTED]"
        assert result["password"] == "[REDACTED]"
        assert result["safe_field"] == "this is safe"
        assert "[REDACTED]" in result["model_path"]
    
    def test_nested_redaction(self):
        """Test nested dictionary redaction."""
        redactor = DataRedactor()
        
        data = {
            "config": {
                "api_key": "secret123",
                "model_dir": "/home/user/.cache/models/",
                "public_info": "safe data",
            },
            "users": [
                {"name": "john", "token": "user_token_123"},
                {"name": "jane", "credential": "cred_456"},
            ]
        }
        
        result = redactor.redact_dict(data)
        
        # Check nested redaction
        assert result["config"]["api_key"] == "[REDACTED]"
        assert "[REDACTED]" in result["config"]["model_dir"]
        assert result["config"]["public_info"] == "safe data"
        
        # Check list redaction
        assert result["users"][0]["token"] == "[REDACTED]"
        assert result["users"][1]["credential"] == "[REDACTED]"
        assert result["users"][0]["name"] == "john"


class TestStructuredLogger:
    """Test structured logging functionality."""
    
    def test_basic_logging(self):
        """Test basic log entry creation."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            logger = StructuredLogger(
                component="test",
                session_id="test_session",
                output_file=f.name,
                enable_console=False,
            )
            
            logger.info("Test message", test_field="test_value", count=42)
            logger.close()
            
            # Read and verify log entry
            with open(f.name, "r") as log_file:
                line = log_file.readline()
                entry = json.loads(line)
                
                assert entry["level"] == "info"
                assert entry["component"] == "test"
                assert entry["session_id"] == "test_session"
                assert entry["message"] == "Test message"
                assert entry["test_field"] == "test_value"
                assert entry["count"] == 42
                assert "timestamp" in entry
                assert "iso_timestamp" in entry
    
    def test_data_redaction(self):
        """Test automatic data redaction in logs."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            logger = StructuredLogger(
                component="test",
                output_file=f.name,
                enable_console=False,
            )
            
            logger.info(
                "Test with sensitive data",
                token="secret123",
                file_path="/home/user/model.bin",
                safe_data="this is safe",
            )
            logger.close()
            
            # Read and verify redaction
            with open(f.name, "r") as log_file:
                line = log_file.readline()
                entry = json.loads(line)
                
                assert entry["token"] == "[REDACTED]"
                assert "[REDACTED]" in entry["file_path"]
                assert "model.bin" in entry["file_path"]  # filename preserved
                assert entry["safe_data"] == "this is safe"
    
    def test_create_logger_factory(self):
        """Test logger factory function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = create_logger(
                component="factory_test",
                session_id="factory_session",
                log_dir=tmpdir,
            )
            
            assert logger.component == "factory_test"
            assert logger.session_id == "factory_session"
            
            # Test logging works
            logger.info("Factory test message")
            
            # Check log file was created
            expected_file = Path(tmpdir) / "factory_test_factory_session.jsonl"
            assert expected_file.exists()


class TestPerformanceMetrics:
    """Test performance metrics collection."""
    
    def test_latency_recording(self):
        """Test latency metric recording."""
        metrics = PerformanceMetrics(component="test")
        
        # Record some latencies
        metrics.record_latency("api_call", 150.0)
        metrics.record_latency("api_call", 200.0)
        metrics.record_latency("api_call", 175.0)
        
        stats = metrics.get_stats("api_call")
        assert stats is not None
        assert stats.count == 3
        assert stats.avg == (150.0 + 200.0 + 175.0) / 3
        assert stats.min == 150.0
        assert stats.max == 200.0
    
    def test_throughput_recording(self):
        """Test throughput metric recording."""
        metrics = PerformanceMetrics(component="test")
        
        metrics.record_throughput("requests_per_sec", 45.0)
        metrics.record_throughput("requests_per_sec", 52.0)
        
        stats = metrics.get_stats("requests_per_sec")
        assert stats is not None
        assert stats.count == 2
        assert stats.avg == 48.5
    
    def test_counters_and_gauges(self):
        """Test counter and gauge metrics."""
        metrics = PerformanceMetrics(component="test")
        
        # Test counters
        metrics.increment_counter("requests")
        metrics.increment_counter("requests", 5)
        
        # Test gauges
        metrics.set_gauge("cpu_usage", 75.5)
        metrics.set_gauge("memory_usage", 1024.0)
        
        summary = metrics.get_all_metrics()
        assert summary["counters"]["requests"] == 6.0
        assert summary["gauges"]["cpu_usage"] == 75.5
        assert summary["gauges"]["memory_usage"] == 1024.0
    
    def test_timer_functionality(self):
        """Test start/end timer functionality."""
        metrics = PerformanceMetrics(component="test")
        
        metrics.start_timer("operation")
        time.sleep(0.01)  # Sleep 10ms
        duration = metrics.end_timer("operation")
        
        # Should be roughly 10ms
        assert 5.0 <= duration <= 50.0  # Allow some variance
        
        stats = metrics.get_stats("operation")
        assert stats is not None
        assert stats.count == 1
    
    def test_timer_error_handling(self):
        """Test timer error handling for non-existent timers."""
        metrics = PerformanceMetrics(component="test")
        
        with pytest.raises(KeyError):
            metrics.end_timer("nonexistent_timer")
    
    def test_threshold_monitoring(self):
        """Test performance threshold monitoring."""
        # Use a mock logger to capture threshold violations
        with patch("loquilex.logging.structured.StructuredLogger") as mock_logger_class:
            mock_logger = mock_logger_class.return_value
            
            metrics = PerformanceMetrics(logger=mock_logger, component="test")
            metrics.set_threshold("latency", warning=100.0, critical=200.0)
            
            # Record below threshold
            metrics.record_latency("latency", 50.0)
            mock_logger.warning.assert_not_called()
            mock_logger.critical.assert_not_called()
            
            # Record warning threshold
            metrics.record_latency("latency", 150.0)
            mock_logger.warning.assert_called_once()
            
            # Record critical threshold
            metrics.record_latency("latency", 250.0)
            mock_logger.critical.assert_called_once()
    
    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        metrics = PerformanceMetrics(component="test")
        
        # Add some data
        metrics.record_latency("test", 100.0)
        metrics.increment_counter("count")
        metrics.set_gauge("gauge", 50.0)
        
        assert metrics.get_stats("test") is not None
        assert "count" in metrics.counters
        assert "gauge" in metrics.gauges
        
        # Reset and verify empty
        metrics.reset()
        
        assert metrics.get_stats("test") is None
        assert len(metrics.counters) == 0
        assert len(metrics.gauges) == 0