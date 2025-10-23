#!/usr/bin/env bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Vault Terraform Initialization${NC}"
echo "================================"
echo ""

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found${NC}"
    exit 1
fi

# Wait for Vault to be ready
echo -e "${BLUE}Waiting for Vault to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=vault -n vault --timeout=300s || {
    echo -e "${RED}Vault pod did not become ready${NC}"
    exit 1
}
echo -e "${GREEN}✓${NC} Vault is ready"
echo ""

# Check if Vault is initialized
echo -e "${BLUE}Checking Vault status...${NC}"
VAULT_STATUS=$(kubectl exec -n vault vault-0 -- vault status -format=json 2>/dev/null || echo '{"initialized": false}')
INITIALIZED=$(echo "$VAULT_STATUS" | grep -o '"initialized":[^,}]*' | cut -d':' -f2 | tr -d ' ')

if [ "$INITIALIZED" = "false" ]; then
    echo -e "${YELLOW}Vault is not initialized yet.${NC}"
    echo ""
    read -p "Do you want to initialize Vault now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${RED}IMPORTANT: Save this output in a secure location!${NC}"
        echo ""
        INIT_OUTPUT=$(kubectl exec -n vault vault-0 -- vault operator init -format=json)
        echo "$INIT_OUTPUT" | jq -r '.unseal_keys_b64[], .root_token'

        ROOT_TOKEN=$(echo "$INIT_OUTPUT" | jq -r '.root_token')

        echo ""
        echo -e "${BLUE}Unsealing Vault...${NC}"
        UNSEAL_KEYS=$(echo "$INIT_OUTPUT" | jq -r '.unseal_keys_b64[]')
        COUNT=0
        while IFS= read -r key; do
            COUNT=$((COUNT + 1))
            kubectl exec -n vault vault-0 -- vault operator unseal "$key" > /dev/null
            echo -e "${GREEN}✓${NC} Unsealed with key $COUNT"
            if [ $COUNT -eq 3 ]; then
                break
            fi
        done <<< "$UNSEAL_KEYS"
    else
        echo "Please initialize Vault manually and run this script again."
        exit 0
    fi
else
    echo -e "${GREEN}✓${NC} Vault is already initialized"

    # Check if sealed
    SEALED=$(echo "$VAULT_STATUS" | grep -o '"sealed":[^,}]*' | cut -d':' -f2 | tr -d ' ')
    if [ "$SEALED" = "true" ]; then
        echo -e "${YELLOW}Vault is sealed. Please unseal it first.${NC}"
        echo "Run: kubectl exec -it -n vault vault-0 -- vault operator unseal"
        exit 1
    fi

    echo ""
    read -p "Enter your Vault root token: " ROOT_TOKEN
    if [ -z "$ROOT_TOKEN" ]; then
        echo -e "${RED}Root token is required${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}Creating Kubernetes secret for Terraform...${NC}"

# Create the secret for Terraform to use
kubectl create secret generic vault-terraform-vars \
    --from-literal=vault_token="$ROOT_TOKEN" \
    --namespace=flux-system \
    --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✓${NC} Secret created in flux-system namespace"
echo ""

echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Commit and push your changes to Git"
echo "2. Flux will automatically:"
echo "   - Deploy Terraform Controller"
echo "   - Run Terraform to configure Vault"
echo "   - Set up Kubernetes auth, policies, and roles"
echo ""
echo "Monitor progress with:"
echo "  flux get helmreleases -A"
echo "  kubectl get terraform -n flux-system"
echo "  kubectl logs -n flux-system -l app.kubernetes.io/name=tf-controller --follow"
echo ""
echo "To see Terraform outputs:"
echo "  kubectl get secret vault-terraform-outputs -n flux-system -o yaml"
