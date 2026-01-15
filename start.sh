#!/bin/bash

# BDI-3 PDF to Word Converter - Quick Start Script

echo "🎯 BDI-3 PDF to Word Converter"
echo "================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Start the application
echo "🚀 Starting the application..."
echo ""
echo "📍 Application will be available at: http://localhost:8080"
echo "📍 Press CTRL+C to stop the server"
echo ""

python3 app.py

