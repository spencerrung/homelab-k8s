# External Secrets Operator

External Secrets Operator (ESO) syncs secrets from external secret management systems (like Vault) into Kubernetes Secrets.

## Overview

ESO watches `ExternalSecret` resources and creates corresponding Kubernetes `Secret` objects by fetching data from external providers.

**Benefits:**
- Keep secrets out of Git
- Centralized secret management
- Automatic secret rotation
- Support for multiple backends (Vault, AWS Secrets Manager, GCP Secret Manager, etc.)

## Architecture

```
External Provider (Vault)
         ↓
    SecretStore (connection config)
         ↓
   ExternalSecret (what to sync)
         ↓
  Kubernetes Secret (created automatically)
         ↓
    Pod (consumes secret)
```

## Setup with Vault

### 1. Ensure Vault is configured

Follow the Vault README to:
- Initialize and unseal Vault
- Enable Kubernetes authentication
- Create policies and roles

### 2. Create a SecretStore

A `SecretStore` configures how ESO connects to Vault:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: myapp  # Create in each namespace that needs secrets
spec:
  provider:
    vault:
      server: "http://vault.vault.svc.cluster.local:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "external-secrets"
          serviceAccountRef:
            name: external-secrets-sa
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: external-secrets-sa
  namespace: myapp
```

See `examples/vault-secret-store.yaml` for a complete example.

### 3. Create an ExternalSecret

An `ExternalSecret` defines what data to sync:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: myapp-secrets
  namespace: myapp
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: myapp-secrets  # Name of K8s Secret to create
    creationPolicy: Owner
  data:
    - secretKey: password      # Key in K8s Secret
      remoteRef:
        key: myapp/config      # Path in Vault: secret/data/myapp/config
        property: db_password  # Field in Vault secret
```

See `examples/external-secret.yaml` for more examples.

### 4. Use the Secret in your Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: myapp
    image: myapp:latest
    env:
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: myapp-secrets  # Created by ExternalSecret
          key: password
```

## ClusterSecretStore vs SecretStore

- **SecretStore**: Namespace-scoped, only accessible within one namespace
- **ClusterSecretStore**: Cluster-scoped, can be used by ExternalSecrets in any namespace

For homelab, SecretStore per namespace is usually simpler and more secure.

## Secret Refresh

ESO automatically refreshes secrets based on `refreshInterval`. When the external secret changes, the Kubernetes Secret is updated automatically.

**Note**: Pods need to be restarted or use a tool like Reloader to pick up updated secrets.

## Examples

### Sync entire secret path

```yaml
spec:
  dataFrom:
    - extract:
        key: myapp/config  # Sync all fields from this Vault path
```

### Template secrets

```yaml
spec:
  target:
    template:
      type: Opaque
      data:
        config.json: |
          {
            "database": "{{ .db_host }}",
            "password": "{{ .db_password }}"
          }
  data:
    - secretKey: db_host
      remoteRef:
        key: myapp/config
        property: db_host
    - secretKey: db_password
      remoteRef:
        key: myapp/config
        property: db_password
```

### Docker registry credentials

```yaml
spec:
  target:
    name: docker-credentials
    template:
      type: kubernetes.io/dockerconfigjson
      data:
        .dockerconfigjson: |
          {
            "auths": {
              "{{ .registry }}": {
                "username": "{{ .username }}",
                "password": "{{ .password }}"
              }
            }
          }
  data:
    - secretKey: registry
      remoteRef:
        key: docker/config
        property: registry
    - secretKey: username
      remoteRef:
        key: docker/config
        property: username
    - secretKey: password
      remoteRef:
        key: docker/config
        property: password
```

## Debugging

### Check ESO logs

```bash
kubectl logs -n external-secrets -l app.kubernetes.io/name=external-secrets
```

### Check ExternalSecret status

```bash
kubectl describe externalsecret -n myapp myapp-secrets
```

### Check if Secret was created

```bash
kubectl get secret -n myapp myapp-secrets
kubectl describe secret -n myapp myapp-secrets
```

### Common issues

**ExternalSecret shows "SecretSyncedError":**
- Check SecretStore configuration
- Verify Vault is accessible: `kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- curl http://vault.vault.svc.cluster.local:8200/v1/sys/health`
- Check Vault authentication is working

**Secret not updating:**
- Check `refreshInterval` setting
- Force refresh: `kubectl annotate externalsecret myapp-secrets force-sync=$(date +%s) -n myapp`

**Permission denied from Vault:**
- Verify Vault role and policy are configured correctly
- Check service account name matches Vault role binding
- Verify secret path exists in Vault

## Security Best Practices

1. **Use namespace-scoped SecretStores** when possible
2. **Principle of least privilege**: Create specific Vault policies per app
3. **Unique service accounts**: Don't reuse the same SA across apps
4. **Short refresh intervals**: Balance between security and API load
5. **Audit**: Monitor ExternalSecret resources for changes
6. **Backup**: Secrets in Vault should be backed up regularly

## Supported Providers

ESO supports many secret backends:
- HashiCorp Vault
- AWS Secrets Manager
- AWS Parameter Store
- GCP Secret Manager
- Azure Key Vault
- IBM Cloud Secrets Manager
- Akeyless
- And many more...

For homelab, Vault is the most common choice for self-hosted secret management.

## Resources

- [ESO Documentation](https://external-secrets.io/)
- [ESO GitHub](https://github.com/external-secrets/external-secrets)
- [API Reference](https://external-secrets.io/latest/api/externalsecret/)
- [Provider Guides](https://external-secrets.io/latest/provider/hashicorp-vault/)
