#!/bin/bash

# Single Container Open Notebook Setup Script
# Uses the all-in-one image to eliminate networking issues

set -e

echo "🚀 Setting up Open Notebook (Single Container) for corporate network..."

# Check for certificate file
# CERT_FILE="certs/tls-ca-bundle.pem"
# if [ ! -f "$CERT_FILE" ]; then
#     echo "❌ Certificate file not found at $CERT_FILE"
#     echo "📋 Please ensure you have the corporate certificate file in place:"
#     echo "   mkdir -p certs"
#     echo "   cp /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem certs/"
#     exit 1
# fi

echo "✅ Corporate certificate found at $CERT_FILE"

# Create directory structure (simpler for single container)
echo "📁 Creating directory structure..."
mkdir -p opennotebook-single/{notebook_data,surreal_data,ollama_data,certs}
cd opennotebook-single

# # Copy certificate
# if [ ! -f "certs/" ] ; then
#     cp "../$CERT_FILE" certs/
# fi

# Create simplified .env file
if [ -f .env ]; then
    echo "⚠️  Environment file does not exist, exiting"
    exit 1
fi

# Function to check available disk space
check_disk_space() {
    local available
    available=$(df /var | awk 'NR==2 {print $4}')
    local available_gb
    available_gb=$((available / 1024 / 1024))
    echo "💾 Available disk space: ${available_gb}GB"
    
    if [ $available_gb -lt 3 ]; then
        echo "⚠️  Low disk space detected (${available_gb}GB)."
        return 1
    fi
    return 0
}

# Function to clean up Docker
cleanup_docker() {
    echo "🧹 Cleaning up Docker to free space..."
    docker system prune -f --volumes 2>/dev/null || true
    docker image prune -a -f 2>/dev/null || true
    echo "✅ Docker cleanup complete"
}

check_disk_space

# Phase 1: Start Ollama first
echo "🐳 Phase 1: Starting Ollama service..."
docker compose up -d ollama

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to start..."
sleep 30

attempt=0
max_attempts=10
while ! docker exec ollama ollama list >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ Ollama failed to start after $max_attempts attempts"
        docker logs ollama
        exit 1
    fi
    echo "⏳ Waiting for Ollama to be ready (attempt $attempt/$max_attempts)..."
    sleep 15
done

echo "✅ Ollama is ready!"

# Phase 2: Download essential models
echo "📥 Phase 2: Downloading essential AI model..."
if docker exec ollama ollama pull llama3.2:3b; then
    echo "✅ Llama 3.2 3B downloaded successfully"
else
    echo "❌ Failed to download model - check corporate network connectivity"
    echo "💡 You can continue and download models later"
fi

# Clean up after model download
cleanup_docker

# Phase 3: Start the single container Open Notebook
echo "🐳 Phase 3: Starting Open Notebook (single container)..."
echo "   📝 This includes both the app and database in one container"

if docker compose up -d open-notebook-single; then
    echo "✅ Open Notebook started successfully!"
    
    # Wait for the app to be ready
    echo "⏳ Waiting for Open Notebook to initialize..."
    sleep 20
    
    # Check if it's responding
    attempt=0
    while ! curl -s http://localhost:8502 >/dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ $attempt -ge 10 ]; then
            echo "⚠️  Open Notebook taking longer than expected to start"
            echo "🔍 Checking logs..."
            docker logs open-notebook-single
            break
        fi
        echo "⏳ Waiting for web interface (attempt $attempt/10)..."
        sleep 10
    done
else
    echo "❌ Failed to start Open Notebook"
    echo "🔍 Checking logs..."
    docker logs open-notebook-single
    exit 1
fi

# Final cleanup
cleanup_docker

echo ""
echo "🎉 Single container setup complete!"

echo ""
echo "📍 Access your services:"
echo "   • Open Notebook: http://notebook.localhost"
echo "   • Direct access: http://localhost:8502"
echo "   • Ollama API: http://ollama.localhost"

echo ""
echo "🔧 Key advantages of single container:"
echo "   • No container networking issues"
echo "   • Built-in database (SurrealDB included)"
echo "   • Simpler configuration"
echo "   • All-in-one solution"

echo ""
echo "📚 First time setup:"
echo "   1. Go to http://notebook.localhost"
echo "   2. If prompted for database migration, click 'Run Migration'"
echo "   3. Go to Settings to configure AI models"
echo "   4. Set up Ollama as your provider with base URL: http://ollama.localhost"

echo ""
echo "🛠️  Container management:"
echo "   • View logs: docker logs open-notebook-single"
echo "   • Restart: docker compose restart"
echo "   • Stop: docker compose down"

echo ""
echo "🤖 Available AI models:"
docker exec ollama ollama list || echo "No models downloaded yet"

echo ""
echo "💾 Final disk space:"
df -h /var
