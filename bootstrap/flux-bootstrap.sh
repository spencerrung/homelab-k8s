#!/usr/bin/env bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="homelab"
GITHUB_USER="${GITHUB_USER:-}"
GITHUB_REPO="${GITHUB_REPO:-homelab-k8s}"
BRANCH="${BRANCH:-main}"

echo -e "${GREEN}Flux Bootstrap Script${NC}"
echo "================================"
echo ""

# Check if flux CLI is installed
if ! command -v flux &> /dev/null; then
    echo -e "${RED}Error: flux CLI not found${NC}"
    echo "Install it with: curl -s https://fluxcd.io/install.sh | sudo bash"
    exit 1
fi

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found${NC}"
    exit 1
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to Kubernetes cluster${NC}"
    echo "Make sure kubectl is configured correctly"
    exit 1
fi

echo -e "${GREEN}✓${NC} Prerequisites check passed"
echo ""

# Get GitHub username if not set
if [ -z "$GITHUB_USER" ]; then
    read -p "Enter your GitHub username: " GITHUB_USER
fi

# Verify GitHub token
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo -e "${YELLOW}Warning: GITHUB_TOKEN environment variable not set${NC}"
    echo "You will be prompted for it during bootstrap"
    echo ""
fi

echo "Configuration:"
echo "  Cluster: $CLUSTER_NAME"
echo "  GitHub User: $GITHUB_USER"
echo "  Repository: $GITHUB_REPO"
echo "  Branch: $BRANCH"
echo ""

read -p "Proceed with bootstrap? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted"
    exit 0
fi

echo ""
echo -e "${GREEN}Bootstrapping Flux...${NC}"

# --read-write-key: image automation pushes tag-bump commits to main
flux bootstrap github \
  --owner="$GITHUB_USER" \
  --repository="$GITHUB_REPO" \
  --branch="$BRANCH" \
  --path="clusters/$CLUSTER_NAME" \
  --personal \
  --read-write-key \
  --components-extra=image-reflector-controller,image-automation-controller

echo ""
echo -e "${GREEN}✓${NC} Flux bootstrap complete!"
echo ""
echo "Checking Flux components..."
flux check

echo ""
echo -e "${GREEN}✓${NC} Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Watch Flux reconciliation: flux get kustomizations --watch"
echo "  2. Check deployed resources: kubectl get kustomizations -A"
echo "  3. View logs: flux logs --follow --all-namespaces"
echo ""
echo "See docs/runbooks/bootstrap.md for the rest of the bring-up."
