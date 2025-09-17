#!/bin/bash
# Test script for Docker deployment
# Verifies Docker setup and basic functionality

set -e

echo "=== LoquiLex Docker Test ==="

# Check prerequisites
echo "Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

echo "Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker prerequisites satisfied"

# Check if UI is built
if [ ! -d "ui/app/dist" ]; then
    echo "📦 Building UI first..."
    make ui-build
else
    echo "✅ UI already built"
fi

# Test basic Docker build
echo "🔨 Testing Docker build (CPU-only)..."
if docker build -t loquilex-test . --quiet; then
    echo "✅ Docker build successful"
    
    # Clean up test image
    docker rmi loquilex-test &> /dev/null || true
else
    echo "❌ Docker build failed"
    echo "This may be due to network connectivity issues in the build environment."
    echo "In a proper Docker environment with internet access, this should work."
    exit 1
fi

# Test Docker Compose configuration
echo "🔍 Validating Docker Compose configuration..."
if docker-compose config > /dev/null 2>&1; then
    echo "✅ Docker Compose configuration valid"
else
    echo "❌ Docker Compose configuration invalid"
    exit 1
fi

echo ""
echo "🎉 All Docker tests passed!"
echo ""
echo "To deploy LoquiLex:"
echo "  CPU-only: make docker-run"
echo "  With GPU:  make docker-gpu"
echo ""
echo "See docs/DOCKER.md for detailed setup instructions."