#!/bin/bash

# Build script for wasmCloud Newheads Provider
# This script builds the provider for wasmCloud deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Building wasmCloud Newheads Provider...${NC}"

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}❌ Cargo not found. Please install Rust.${NC}"
    exit 1
fi

# Check if wash is installed
if ! command -v wash &> /dev/null; then
    echo -e "${YELLOW}⚠️  wash not found. Installing wash...${NC}"
    cargo install wash-cli
fi

echo -e "${YELLOW}📦 Building provider binary...${NC}"

# Build the provider binary
cargo build --release --bin newheads-provider

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to build provider binary${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Provider binary built successfully${NC}"

# Create provider archive
echo -e "${YELLOW}📦 Creating provider archive...${NC}"

# Create the provider archive using wash
wash par create \
    --arch x86_64-linux \
    --binary ./target/release/newheads-provider \
    --capid "ekko:newheads" \
    --name "Newheads Provider" \
    --vendor "ekko.zone" \
    --version "0.1.0" \
    --revision 1 \
    --destination ./target/release/newheads-provider.par.gz

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create provider archive${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Provider archive created: ./target/release/newheads-provider.par.gz${NC}"

# Validate the provider archive
echo -e "${YELLOW}🔍 Validating provider archive...${NC}"

wash par inspect ./target/release/newheads-provider.par.gz

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Provider archive validation failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Provider archive validated successfully${NC}"

# Display deployment instructions
echo -e "${BLUE}🚀 Deployment Instructions:${NC}"
echo -e "${YELLOW}1. Start wasmCloud host:${NC}"
echo "   wash up"
echo ""
echo -e "${YELLOW}2. Deploy the application:${NC}"
echo "   wash app deploy wasmcloud-app.yaml"
echo ""
echo -e "${YELLOW}3. Check provider status:${NC}"
echo "   wash ctl get providers"
echo ""
echo -e "${YELLOW}4. View logs:${NC}"
echo "   wash ctl logs"
echo ""
echo -e "${GREEN}🎉 Build completed successfully!${NC}"
