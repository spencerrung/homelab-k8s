# Vault Auto-Unseal Configuration

This directory contains the auto-unseal configuration for Vault in the homelab environment.

## How It Works

Auto-unseal is implemented using a sidecar container that:
1. Monitors Vault's seal status every 30 seconds
2. Automatically unseals Vault if it detects it's sealed
3. Uses unseal keys stored in a Kubernetes secret

## Components

### 1. Unseal Keys Secret
Created by `bootstrap/init-vault-terraform.sh`:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: vault-unseal-keys
  namespace: vault
data:
  key1: <base64-encoded-unseal-key>
  key2: <base64-encoded-unseal-key>
  key3: <base64-encoded-unseal-key>
```

### 2. Auto-Unseal Sidecar
A lightweight container running alongside Vault that:
- Runs continuously in the background
- Checks Vault status every 30 seconds
- Unseals automatically when sealed state is detected
- Uses minimal resources (10m CPU, 32Mi RAM)

### 3. Volume Mount
The unseal keys secret is mounted read-only into both:
- Main Vault container (for manual operations)
- Auto-unseal sidecar (for automatic unsealing)

## Security Considerations

⚠️ **IMPORTANT**: This auto-unseal approach is designed for **homelab convenience**, not production security!

### Security Trade-offs

**Pros:**
- ✅ Automatic unsealing on pod restart
- ✅ No manual intervention needed
- ✅ Works offline (no external dependencies)
- ✅ Simple to manage

**Cons:**
- ❌ Unseal keys stored in Kubernetes (same cluster as Vault)
- ❌ Anyone with cluster admin access can read the keys
- ❌ Not compliant with enterprise security requirements
- ❌ Doesn't protect against cluster compromise

### Why This is Acceptable for Homelabs

1. **Convenience > Security**: Homelabs prioritize ease of use
2. **Physical Security**: Your cluster is in your home, not the cloud
3. **No Compliance Requirements**: Not subject to SOC2, PCI-DSS, etc.
4. **Learning Environment**: Good for understanding Vault concepts

### Production Alternatives

For production use, consider:

**Cloud KMS (Best)**:
```hcl
seal "gcpckms" {
  project     = "my-project"
  region      = "us-east1"
  key_ring    = "vault"
  crypto_key  = "vault-key"
}
```

**Transit Seal (Good)**:
- Use a separate Vault instance as KMS
- Primary Vault uses Transit seal pointing to KMS Vault
- KMS Vault must be manually unsealed

**HSM (Enterprise)**:
- Hardware Security Module integration
- FIPS 140-2 compliant
- Expensive but most secure

## How to Disable Auto-Unseal

If you want manual unsealing instead:

1. **Remove the overlay:**
   ```yaml
   # infrastructure/overlays/homelab/kustomization.yaml
   resources:
     - ../../base/vault  # Use base instead of ./vault
   ```

2. **Delete the unseal keys secret:**
   ```bash
   kubectl delete secret vault-unseal-keys -n vault
   ```

3. **Unseal manually after restarts:**
   ```bash
   kubectl exec -it -n vault vault-0 -- vault operator unseal
   # Repeat 3 times with different keys
   ```

## Backup and Recovery

### Backup Unseal Keys

**Option 1: Export to file (store securely!)**
```bash
kubectl get secret vault-unseal-keys -n vault -o yaml > vault-keys-backup.yaml
# Encrypt this file!
gpg --encrypt --recipient your@email.com vault-keys-backup.yaml
# Store encrypted file in password manager or safe location
```

**Option 2: Export individual keys**
```bash
kubectl get secret vault-unseal-keys -n vault \
  -o jsonpath='{.data.key1}' | base64 -d
# Save to password manager
```

### Restore Unseal Keys

If you lose the secret but have a backup:
```bash
# From backup file
kubectl apply -f vault-keys-backup.yaml

# Or recreate manually
kubectl create secret generic vault-unseal-keys \
  --from-literal=key1="<unseal-key-1>" \
  --from-literal=key2="<unseal-key-2>" \
  --from-literal=key3="<unseal-key-3>" \
  --namespace=vault
```

### If You Lose All Unseal Keys

❌ **You cannot recover Vault data without unseal keys!**

This is why you should:
1. Save unseal keys from initial `vault operator init` output
2. Store them in a password manager
3. Keep encrypted backups off-cluster
4. Test your backup/restore process

## Monitoring Auto-Unseal

### Check if auto-unseal is working

```bash
# Check Vault status
kubectl exec -n vault vault-0 -- vault status

# View auto-unseal sidecar logs
kubectl logs -n vault vault-0 -c auto-unseal --tail=50

# Restart Vault to test auto-unseal
kubectl delete pod -n vault vault-0
# Watch it unseal automatically
kubectl logs -n vault vault-0 -c auto-unseal -f
```

### Expected Logs

**Normal operation:**
```
Auto-unseal sidecar started
Vault is sealed, attempting to unseal...
Unseal attempt completed
```

**If keys missing:**
```
Unseal keys not found, skipping auto-unseal
```

## Troubleshooting

### Auto-unseal not working

**Check 1: Secret exists**
```bash
kubectl get secret vault-unseal-keys -n vault
```

**Check 2: Keys are valid**
```bash
# Manually test unseal
kubectl exec -it -n vault vault-0 -- vault operator unseal
# Paste key1 from secret
```

**Check 3: Sidecar is running**
```bash
kubectl get pod vault-0 -n vault -o jsonpath='{.spec.containers[*].name}'
# Should show: vault auto-unseal
```

**Check 4: Logs for errors**
```bash
kubectl logs -n vault vault-0 -c auto-unseal
```

### Vault stays sealed

Possible causes:
1. Unseal keys secret doesn't exist (not created yet)
2. Wrong keys in secret
3. Sidecar not deployed (check kustomization)
4. Network issue between sidecar and Vault

### Want faster unsealing?

Edit the sidecar sleep interval:
```yaml
# auto-unseal-patch.yaml
while true; do
  sleep 10  # Check every 10 seconds instead of 30
  ...
done
```

## Rekeying Vault

If you need to change unseal keys:

```bash
# 1. Generate new keys
kubectl exec -it -n vault vault-0 -- vault operator rekey -init

# 2. Complete rekey process
kubectl exec -it -n vault vault-0 -- vault operator rekey

# 3. Update the secret with new keys
kubectl create secret generic vault-unseal-keys \
  --from-literal=key1="<new-key-1>" \
  --from-literal=key2="<new-key-2>" \
  --from-literal=key3="<new-key-3>" \
  --namespace=vault \
  --dry-run=client -o yaml | kubectl apply -f -

# 4. Restart Vault pod to pick up new keys
kubectl delete pod -n vault vault-0
```

## Best Practices

1. **Keep Original Keys**: Always save the keys from initial `vault operator init`
2. **Off-Cluster Backup**: Store encrypted backup outside the cluster
3. **Test Recovery**: Periodically test unsealing with backed-up keys
4. **Monitor Logs**: Watch auto-unseal logs for anomalies
5. **Limit Access**: Use RBAC to restrict who can read the unseal keys secret
6. **Consider Rotation**: Rekey Vault annually or after personnel changes

## Migration to Production Auto-Unseal

When you're ready for production-grade auto-unseal:

1. **Choose a KMS provider** (AWS KMS, GCP KMS, Azure Key Vault)
2. **Configure Vault seal stanza** in Terraform or Helm values
3. **Migrate seal type** using `vault operator unseal -migrate`
4. **Remove sidecar** by reverting to base Vault configuration
5. **Delete unseal keys secret** (no longer needed)

Example production seal config:
```yaml
# Helm values
server:
  ha:
    enabled: true
    config: |
      seal "awskms" {
        region     = "us-east-1"
        kms_key_id = "arn:aws:kms:us-east-1:..."
      }
```

## Additional Resources

- [Vault Auto-Unseal Documentation](https://developer.hashicorp.com/vault/docs/concepts/seal#auto-unseal)
- [Vault Seal Migration](https://developer.hashicorp.com/vault/tutorials/operations/seal-migration)
- [Kubernetes Seal](https://developer.hashicorp.com/vault/docs/configuration/seal/kubernetes)
