# Vault Setup

HashiCorp Vault for secrets management in the homelab cluster.

## Configuration

Vault is deployed in **standalone mode** with file-based storage. This is suitable for homelab use but for production you should configure HA mode with proper backend storage (Consul, etcd, etc.).

## Initial Setup

After Flux deploys Vault, you need to initialize and unseal it:

### 1. Initialize Vault

```bash
# Get a shell in the Vault pod
kubectl exec -it -n vault vault-0 -- /bin/sh

# Initialize Vault (do this only once!)
vault operator init

# Save the output! You'll get:
# - 5 unseal keys
# - 1 root token
# Store these securely - you'll need them to unseal Vault after restarts
```

**IMPORTANT**: Save the unseal keys and root token in a secure location (password manager, encrypted file, etc.). You cannot recover them if lost!

### 2. Unseal Vault

Vault starts in a sealed state and needs to be unsealed after every restart:

```bash
# You need to provide 3 of the 5 unseal keys
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-1>
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-2>
kubectl exec -it -n vault vault-0 -- vault operator unseal <key-3>

# Check status
kubectl exec -it -n vault vault-0 -- vault status
```

### 3. Login and Configure

```bash
# Login with root token
kubectl exec -it -n vault vault-0 -- vault login <root-token>

# Enable KV v2 secrets engine
kubectl exec -it -n vault vault-0 -- vault secrets enable -path=secret kv-v2

# Verify
kubectl exec -it -n vault vault-0 -- vault secrets list
```

## Kubernetes Authentication Setup

To allow External Secrets Operator to read from Vault:

### 1. Enable Kubernetes auth

```bash
kubectl exec -it -n vault vault-0 -- vault auth enable kubernetes
```

### 2. Configure Kubernetes auth

```bash
# Get Kubernetes cluster info
kubectl exec -it -n vault vault-0 -- sh -c '
vault write auth/kubernetes/config \
    kubernetes_host="https://$KUBERNETES_PORT_443_TCP_ADDR:443"
'
```

### 3. Create a policy for External Secrets

```bash
kubectl exec -it -n vault vault-0 -- sh -c '
vault policy write external-secrets - <<EOF
path "secret/data/*" {
  capabilities = ["read"]
}
path "secret/metadata/*" {
  capabilities = ["list"]
}
EOF
'
```

### 4. Create a role for External Secrets

```bash
kubectl exec -it -n vault vault-0 -- sh -c '
vault write auth/kubernetes/role/external-secrets \
    bound_service_account_names=external-secrets-sa \
    bound_service_account_namespaces=* \
    policies=external-secrets \
    ttl=24h
'
```

## Testing

### Add a test secret

```bash
kubectl exec -it -n vault vault-0 -- vault kv put secret/test password=mypassword
```

### Read the secret

```bash
kubectl exec -it -n vault vault-0 -- vault kv get secret/test
```

## Auto-Unseal (Optional)

For homelab convenience, you might want to set up auto-unseal. Options:
- **Transit auto-unseal**: Use another Vault instance
- **Cloud KMS**: AWS KMS, GCP KMS, Azure Key Vault
- **Script-based**: Automated unseal on pod start (less secure)

For homelabs, manual unseal or a simple automated script is usually acceptable.

## Access Vault UI

The Vault UI is available but not exposed externally by default.

### Port-forward to access UI

```bash
kubectl port-forward -n vault svc/vault 8200:8200
```

Then visit: http://localhost:8200

Login with your root token.

## Backup

Vault data is stored in a PersistentVolume. Make sure to:
1. Back up the PV regularly
2. Back up your unseal keys and root token separately
3. Consider periodic snapshots if using a supported backend

## Security Notes

- Never commit unseal keys or tokens to Git
- Rotate the root token regularly
- Create separate policies for each application
- Use namespaced service accounts for authentication
- Consider using Vault Agent for automatic secret injection
- Monitor Vault audit logs

## Common Commands

```bash
# Check status
kubectl exec -it -n vault vault-0 -- vault status

# List secrets
kubectl exec -it -n vault vault-0 -- vault kv list secret/

# Get a secret
kubectl exec -it -n vault vault-0 -- vault kv get secret/path/to/secret

# Put a secret
kubectl exec -it -n vault vault-0 -- vault kv put secret/path/to/secret key=value

# Delete a secret
kubectl exec -it -n vault vault-0 -- vault kv delete secret/path/to/secret
```

## Troubleshooting

### Pod won't start
- Check logs: `kubectl logs -n vault vault-0`
- Verify PVC is bound: `kubectl get pvc -n vault`

### Can't unseal
- Ensure you're using the correct unseal keys
- Need 3 different keys (threshold)
- Check Vault logs for errors

### Authentication failures
- Verify Kubernetes auth is enabled
- Check policy and role configuration
- Ensure service account exists and is referenced correctly

## Resources

- [Vault Documentation](https://www.vaultproject.io/docs)
- [Vault on Kubernetes Guide](https://www.vaultproject.io/docs/platform/k8s)
- [Kubernetes Auth Method](https://www.vaultproject.io/docs/auth/kubernetes)
