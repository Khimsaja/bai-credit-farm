#!/bin/bash
# Quick setup for B.AI Credit Farmer
set -e

echo "🤖 B.AI Credit Farmer — Setup"
echo "=============================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Install Python 3.8+ first."
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q playwright

echo "🌐 Installing Chromium browser..."
playwright install chromium --with-deps 2>/dev/null || playwright install chromium

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Run examples:"
echo "  Single:  python bai-farm.py --email user@domain.com --password mypass"
echo "  Batch:   python bai-farm.py --range 1-100 --domain giosin.com --password mypass"
echo ""
echo "📁 Keys will be saved to ./bai-keys/"
