# Tekton CI/CD Pipeline for Gitea

This directory contains Tekton pipelines for building and pushing container images from Gitea repositories to Gitea's container registry.

## Architecture

The pipeline uses **internal cluster networking** for security - webhooks never leave the cluster.

```
Gitea Pod → http://el-gitea-listener.tekton-pipelines.svc.cluster.local:8080 → EventListener → Pipeline
```

## Setup Instructions

### 1. Store Secrets in Vault

```bash
# Generate a Gitea access token
# Go to Gitea → Settings → Applications → Generate New Token
# Scopes needed: write:package

# Store registry credentials in Vault
vault kv put gitea/registry-credentials \
  username="your-gitea-username" \
  token="your-gitea-token"

# Generate and store webhook secret
vault kv put gitea/webhook-secret \
  secret="$(openssl rand -hex 32)"
```

### 2. Configure Gitea Webhook (Internal Service)

In your Gitea repository:
1. Go to **Settings → Webhooks → Add Webhook → Gitea**
2. Configure:
   - **Target URL**: `http://el-gitea-listener.tekton-pipelines.svc.cluster.local:8080`
   - **HTTP Method**: POST
   - **POST Content Type**: application/json
   - **Secret**: Get from Vault: `vault kv get -field=secret gitea/webhook-secret`
   - **Trigger On**: Push events
   - **Branch filter**: `main` (or leave empty for all)
   - **Active**: ✓ checked
3. Click **Add Webhook**

### 3. Test the Webhook

Click "Test Delivery" on the webhook configuration page, or push a commit to your repo.

## How It Works

### Automated (Webhook Trigger)
```
1. Developer pushes to main branch
2. Gitea sends webhook internally to EventListener
3. EventListener validates webhook signature
4. TriggerBinding extracts repo URL, commit SHA, etc.
5. TriggerTemplate creates PipelineRun
6. Pipeline:
   a. Clones the repository
   b. Builds container image with Buildah
   c. Pushes to code.alucard.dev/owner/repo:commit-sha
```

### Manual Trigger

```bash
kubectl create -f - <<EOF
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: manual-build-
  namespace: tekton-pipelines
spec:
  serviceAccountName: tekton-build-sa
  pipelineRef:
    name: build-and-push
  params:
    - name: repo-url
      value: https://code.alucard.dev/your-username/your-repo.git
    - name: revision
      value: main
    - name: image-reference
      value: code.alucard.dev/your-username/your-repo:latest
  workspaces:
    - name: shared-data
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources:
            requests:
              storage: 1Gi
    - name: docker-credentials
      secret:
        secretName: gitea-docker-credentials
EOF
```

## Monitoring

### View Pipeline Runs
```bash
# List all pipeline runs
kubectl get pipelinerun -n tekton-pipelines

# Watch pipeline run progress
kubectl get pipelinerun -n tekton-pipelines -w

# Get detailed info
kubectl describe pipelinerun <name> -n tekton-pipelines
```

### View Logs
```bash
# Get logs for a pipeline run (all containers)
kubectl logs -n tekton-pipelines -l tekton.dev/pipelineRun=<name> --all-containers -f

# Tekton Dashboard (Web UI)
# Access at: https://tekton.alucard.dev
```

## Troubleshooting

### Webhook Not Triggering

1. Check EventListener is running:
   ```bash
   kubectl get eventlistener -n tekton-pipelines
   kubectl get pods -n tekton-pipelines -l eventlistener=gitea-listener
   ```

2. Check EventListener logs:
   ```bash
   kubectl logs -n tekton-pipelines -l eventlistener=gitea-listener
   ```

3. Test webhook from Gitea:
   - Go to repo Settings → Webhooks
   - Click on your webhook
   - Scroll to "Recent Deliveries"
   - Click "Test Delivery"

### Build Failures

1. Check PipelineRun status:
   ```bash
   kubectl get pipelinerun -n tekton-pipelines
   ```

2. View logs:
   ```bash
   kubectl logs -n tekton-pipelines <pipelinerun-pod> --all-containers
   ```

3. Common issues:
   - Missing Dockerfile in repo root
   - Insufficient registry permissions (check token scopes)
   - Build context issues (check CONTEXT parameter)

## Image Tags

By default, images are tagged with the **commit SHA**:
```
code.alucard.dev/owner/repo:abc123def456
```

To customize tagging, modify the `image-reference` parameter in `triggers.yaml`.

## Security

- ✅ Webhook traffic stays within cluster (no internet exposure)
- ✅ Webhook signatures validated using shared secret
- ✅ Registry credentials stored in Vault
- ✅ ServiceAccount with minimal permissions
- ✅ TLS verification on registry push (set TLSVERIFY: "true" in production)

## Components

- **git-clone Task**: Clones repository from Gitea
- **buildah Task**: Builds and pushes OCI container images
- **build-and-push Pipeline**: Orchestrates the full workflow
- **EventListener**: Receives and validates webhooks
- **TriggerBinding**: Extracts data from webhook payload
- **TriggerTemplate**: Creates PipelineRun from webhook data
