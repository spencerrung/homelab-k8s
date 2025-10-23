# Managing Infrastructure with Terraform

This guide explains how to use Terraform Controller to manage your infrastructure as code in a GitOps workflow.

## Overview

Infrastructure configuration (Vault, cloud resources, etc.) is managed using Terraform code stored in Git. Flux Terraform Controller automatically applies changes and keeps infrastructure in sync.

**Workflow:**
1. Write Terraform code in this repository
2. Commit and push to Git
3. Flux Terraform Controller automatically applies it
4. Infrastructure stays in sync (drift detection)

## Directory Structure

```
infrastructure/
├── base/
│   ├── vault/
│   │   ├── terraform/           # Terraform code for Vault
│   │   │   ├── main.tf         # Main configuration
│   │   │   └── ...
│   │   └── terraform-vault-config.yaml  # Terraform CRD
│   └── other-component/
│       └── terraform/           # More Terraform configurations
└── overlays/
    └── homelab/
```

## Adding New Infrastructure

### Example: Configure a New Vault Secret Path

1. **Edit the Terraform code:**

```bash
# Edit infrastructure/base/vault/terraform/main.tf
```

Add a new resource:

```hcl
# Create a new policy for myapp
resource "vault_policy" "myapp" {
  name = "myapp"

  policy = <<EOT
path "secret/data/myapp/*" {
  capabilities = ["read"]
}
EOT
}

# Create a role for myapp
resource "vault_kubernetes_auth_backend_role" "myapp" {
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "myapp"
  bound_service_account_names      = ["myapp-sa"]
  bound_service_account_namespaces = ["myapp"]
  token_ttl                        = 3600
  token_policies                   = [vault_policy.myapp.name]
}
```

2. **Commit and push:**

```bash
git add infrastructure/base/vault/terraform/main.tf
git commit -m "Add Vault policy and role for myapp"
git push
```

3. **Watch Terraform apply:**

```bash
# Watch Flux reconcile
flux get kustomizations --watch

# Check Terraform status
kubectl get terraform vault-config -n flux-system

# View Terraform logs
kubectl logs -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config --follow
```

4. **Verify changes:**

```bash
kubectl exec -it -n vault vault-0 -- vault policy read myapp
kubectl exec -it -n vault vault-0 -- vault read auth/kubernetes/role/myapp
```

## Creating a New Terraform Configuration

For new infrastructure components (not Vault):

### 1. Create Terraform Directory

```bash
mkdir -p infrastructure/base/mycomponent/terraform
```

### 2. Write Terraform Code

```hcl
# infrastructure/base/mycomponent/terraform/main.tf
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

resource "aws_s3_bucket" "backup" {
  bucket = "homelab-backup-${var.cluster_name}"
}

output "bucket_name" {
  value = aws_s3_bucket.backup.id
}
```

### 3. Create Terraform CRD

```yaml
# infrastructure/base/mycomponent/terraform-mycomponent.yaml
---
apiVersion: infra.contrib.fluxcd.io/v1alpha2
kind: Terraform
metadata:
  name: mycomponent
  namespace: flux-system
spec:
  interval: 10m
  approvePlan: auto

  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system

  path: ./infrastructure/base/mycomponent/terraform

  vars:
    - name: cluster_name
      value: homelab

  varsFrom:
    - kind: Secret
      name: aws-credentials
      varsKeys:
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY

  writeOutputsToSecret:
    name: mycomponent-outputs
    outputs:
      - bucket_name

  runnerPodTemplate:
    spec:
      containers:
        - name: tf-runner
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

### 4. Add to Kustomization

```yaml
# infrastructure/base/mycomponent/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - terraform-mycomponent.yaml
```

```yaml
# infrastructure/base/kustomization.yaml
resources:
  - sources/
  - tf-controller/
  - vault/
  - mycomponent/  # Add this line
```

### 5. Create Secrets (if needed)

```bash
kubectl create secret generic aws-credentials \
  --from-literal=AWS_ACCESS_KEY_ID=xxx \
  --from-literal=AWS_SECRET_ACCESS_KEY=yyy \
  --namespace=flux-system
```

### 6. Commit and Push

```bash
git add infrastructure/
git commit -m "Add mycomponent Terraform configuration"
git push
```

## Managing Sensitive Variables

### Option 1: Kubernetes Secrets (Current Approach)

```bash
kubectl create secret generic terraform-vars \
  --from-literal=api_token=xxx \
  --namespace=flux-system
```

Reference in Terraform CRD:
```yaml
varsFrom:
  - kind: Secret
    name: terraform-vars
    varsKeys:
      - api_token
```

### Option 2: External Secrets (Better for Production)

Create an ExternalSecret that syncs from Vault:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: terraform-vars
  namespace: flux-system
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: terraform-vars
  data:
    - secretKey: api_token
      remoteRef:
        key: terraform/credentials
        property: api_token
```

Then Terraform Controller uses the auto-generated secret.

## Drift Detection

Terraform Controller continuously checks for drift:

1. Every `interval` (default 10m), it runs `terraform plan`
2. If drift is detected and `approvePlan: auto`, it applies automatically
3. If `approvePlan: plan-only`, you must manually approve

### View Drift

```bash
# Check status
kubectl describe terraform vault-config -n flux-system

# Look for "Drift Detected" events
kubectl get events -n flux-system --field-selector involvedObject.name=vault-config
```

### Manual Approval

If using `approvePlan: plan-only`:

```bash
# Review the plan
kubectl describe terraform vault-config -n flux-system

# Approve
kubectl annotate terraform vault-config \
  -n flux-system \
  infra.contrib.fluxcd.io/apply=true
```

## State Management

By default, state is stored in Kubernetes secrets. For production, use remote backends.

### Kubernetes Backend (Recommended for Homelab)

```hcl
terraform {
  backend "kubernetes" {
    secret_suffix     = "state"
    in_cluster_config = true
    namespace         = "flux-system"
  }
}
```

### S3 Backend (Recommended for Production)

```hcl
terraform {
  backend "s3" {
    bucket = "terraform-state"
    key    = "homelab/vault.tfstate"
    region = "us-east-1"
  }
}
```

## Upgrading Infrastructure

### Updating Provider Versions

```hcl
terraform {
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "~> 4.1"  # Update version
    }
  }
}
```

Commit and push - Terraform Controller will upgrade automatically.

### Testing Changes Locally (Optional)

```bash
# Clone the repo
cd infrastructure/base/vault/terraform

# Set variables
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=your-token

# Test plan
terraform init
terraform plan

# Don't apply locally - let Flux do it
```

## Rollback

If a Terraform change breaks something:

### Option 1: Git Revert

```bash
git revert HEAD
git push
```

Flux will apply the previous state.

### Option 2: Manual Terraform

```bash
# Get into runner pod (if still running)
kubectl get pods -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config

# Exec into it
kubectl exec -it <pod-name> -n flux-system -- sh

# Run terraform commands
terraform state list
terraform state rm ...
```

### Option 3: Destroy and Recreate

```bash
# Delete the Terraform resource (doesn't destroy infrastructure by default)
kubectl delete terraform vault-config -n flux-system

# Fix the code in Git
git commit -m "Fix configuration"
git push

# Recreate by re-adding to kustomization
```

## Debugging

### Terraform Plan Failed

```bash
# Check runner pod logs
kubectl logs -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config

# Check controller logs
kubectl logs -n flux-system -l app.kubernetes.io/name=tf-controller
```

### State Locked

```bash
# View the runner pod
kubectl get pods -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config

# Force unlock (BE CAREFUL!)
kubectl exec -it <pod> -n flux-system -- terraform force-unlock <lock-id>
```

### Authentication Issues

Ensure secrets are created and referenced correctly:

```bash
kubectl get secret -n flux-system
kubectl describe terraform vault-config -n flux-system
```

## Best Practices

1. **Small Changes**: Make incremental changes, not big-bang updates
2. **Test Locally**: Validate syntax with `terraform validate` before pushing
3. **Use Variables**: Parameterize configurations for reusability
4. **Document**: Add comments explaining complex resources
5. **Outputs**: Use outputs to pass data to other systems
6. **Dependencies**: Use `dependsOn` to ensure proper ordering
7. **Resource Limits**: Set appropriate limits on runner pods
8. **Remote State**: Use remote backends for team environments
9. **Plan Review**: Consider `plan-only` for critical infrastructure
10. **GitOps**: Never apply Terraform manually - always through Git

## Migration to GitLab CI (Future)

When you set up GitLab CI:

### Option 1: Keep Terraform Controller

Use GitLab CI for other tasks, keep Terraform Controller for automatic drift correction.

### Option 2: GitLab CI Only

1. Create `.gitlab-ci.yml`:
```yaml
terraform:
  stage: deploy
  script:
    - terraform init
    - terraform plan
    - terraform apply -auto-approve
  only:
    - main
```

2. Remove Terraform CRDs from Git
3. Disable Terraform Controller (or keep for drift detection)

The Terraform code itself doesn't change - just the execution method.

## Resources

- [Terraform Controller Docs](https://weaveworks.github.io/tf-controller/)
- [Terraform Best Practices](https://www.terraform.io/docs/cloud/guides/recommended-practices/index.html)
- [Vault Provider Docs](https://registry.terraform.io/providers/hashicorp/vault/latest/docs)
