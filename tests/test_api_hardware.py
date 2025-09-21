"""Test hardware snapshot API endpoint."""

import pytest
from fastapi.testclient import TestClient

from loquilex.api.server import app


class TestHardwareEndpoint:
    """Test hardware snapshot endpoint."""
    
    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)
    
    def test_hardware_snapshot_endpoint_success(self, client):
        """Test hardware snapshot endpoint returns valid data."""
        response = client.get("/hardware/snapshot")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "cpu" in data
        assert "gpus" in data
        assert "audio_devices" in data
        assert "memory_total_gb" in data
        assert "memory_available_gb" in data
        assert "platform_info" in data
        assert "overall_status" in data
        assert "overall_score" in data
        assert "warnings" in data
        
        # Validate CPU data
        cpu = data["cpu"]
        assert "name" in cpu
        assert "cores_logical" in cpu
        assert "cores_physical" in cpu
        assert "meets_threshold" in cpu
        assert "warnings" in cpu
        assert isinstance(cpu["cores_logical"], int)
        assert cpu["cores_logical"] >= 1
        assert isinstance(cpu["warnings"], list)
        
        # Validate GPU data
        gpus = data["gpus"]
        assert isinstance(gpus, list)
        assert len(gpus) >= 1
        for gpu in gpus:
            assert "name" in gpu
            assert "cuda_available" in gpu
            assert "meets_threshold" in gpu
            assert "warnings" in gpu
            assert isinstance(gpu["cuda_available"], bool)
            assert isinstance(gpu["warnings"], list)
        
        # Validate audio device data
        audio_devices = data["audio_devices"]
        assert isinstance(audio_devices, list)
        assert len(audio_devices) >= 1
        for device in audio_devices:
            assert "name" in device
            assert "device_id" in device
            assert "is_available" in device
            assert "warnings" in device
            assert isinstance(device["device_id"], int)
            assert isinstance(device["is_available"], bool)
            assert isinstance(device["warnings"], list)
        
        # Validate overall status
        assert data["overall_status"] in ["excellent", "good", "fair", "poor", "unusable"]
        assert isinstance(data["overall_score"], int)
        assert 0 <= data["overall_score"] <= 100
        
        # Validate memory
        assert isinstance(data["memory_total_gb"], (int, float))
        assert isinstance(data["memory_available_gb"], (int, float))
        assert data["memory_total_gb"] > 0
        assert data["memory_available_gb"] >= 0
        
        # Validate platform info
        platform_info = data["platform_info"]
        assert isinstance(platform_info, dict)
        assert "system" in platform_info
        assert "python_version" in platform_info
        
        # Validate warnings
        warnings = data["warnings"]
        assert isinstance(warnings, list)
    
    def test_hardware_snapshot_endpoint_contains_threshold_info(self, client):
        """Test hardware snapshot includes threshold validation."""
        response = client.get("/hardware/snapshot")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that threshold validation occurred
        cpu = data["cpu"]
        assert isinstance(cpu["meets_threshold"], bool)
        
        for gpu in data["gpus"]:
            assert isinstance(gpu["meets_threshold"], bool)
        
        # Overall score should be calculated
        assert 0 <= data["overall_score"] <= 100