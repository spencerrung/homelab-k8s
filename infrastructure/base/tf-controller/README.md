# Terraform Controller (tf-controller)

Flux Terraform Controller enables GitOps for Terraform. It runs Terraform in your Kubernetes cluster and keeps infrastructure in sync with your Git repository.

## Overview

tf-controller watches `Terraform` custom resources and:
1. Pulls Terraform code from Git
2. Runs `terraform plan`
3. Applies changes automatically (if configured)
4. Continuously reconciles to prevent drift
5. Stores state in Kubernetes secrets or remote backends

## Benefits

- **GitOps-native**: Terraform runs in-cluster, managed by Flux
- **Automatic drift detection**: Continuously reconciles state
- **No external CI/CD needed**: Self-contained workflow
- **State management**: Built-in state storage
- **Branch planner**: Automatic plan comments on PRs (optional)

## Architecture

```
Git Repository (Terraform code)
        ↓
  GitRepository (Flux source)
        ↓
  Terraform CRD (what to apply)
        ↓
  tf-controller (watches & executes)
        ↓
  Runner Pod (runs terraform)
        ↓
  Target Infrastructure (Vault, etc.)
```

## Basic Usage

### 1. Create Terraform Code

Place your Terraform code in the repository:

```
infrastructure/base/vault/terraform/
├── main.tf
├── variables.tf
└── outputs.tf
```

### 2. Create a Terraform Resource

```yaml
apiVersion: infra.contrib.fluxcd.io/v1alpha2
kind: Terraform
metadata:
  name: my-infrastructure
  namespace: flux-system
spec:
  interval: 10m

  sourceRef:
    kind: GitRepository
    name: flux-system

  path: ./infrastructure/base/vault/terraform

  approvePlan: auto  # or "plan-only" for manual approval

  vars:
    - name: region
      value: us-east-1

  varsFrom:
    - kind: Secret
      name: terraform-vars
```

### 3. Commit and Push

```bash
git add .
git commit -m "Add Terraform configuration"
git push
```

Flux will automatically apply the Terraform!

## Terraform Resource Spec

### Key Fields

**interval**: How often to reconcile (check for drift)
```yaml
interval: 10m
```

**sourceRef**: Where to get Terraform code
```yaml
sourceRef:
  kind: GitRepository
  name: flux-system
  namespace: flux-system
```

**path**: Path to Terraform code in the repository
```yaml
path: ./terraform/vault
```

**approvePlan**: Approval mode
- `auto`: Automatically apply plans
- `plan-only`: Generate plan but don't apply (requires manual approval)

```yaml
approvePlan: auto
```

**vars**: Inline variables
```yaml
vars:
  - name: environment
    value: production
```

**varsFrom**: Variables from Secrets/ConfigMaps
```yaml
varsFrom:
  - kind: Secret
    name: terraform-secrets
    varsKeys:
      - api_token
```

**writeOutputsToSecret**: Store Terraform outputs
```yaml
writeOutputsToSecret:
  name: terraform-outputs
  outputs:
    - vpc_id
    - subnet_ids
```

**dependsOn**: Wait for other resources
```yaml
dependsOn:
  - name: infrastructure
    namespace: flux-system
```

**destroyResourcesOnDeletion**: Terraform destroy on delete
```yaml
destroyResourcesOnDeletion: false  # Be careful!
```

## State Management

By default, state is stored in Kubernetes secrets in the same namespace as the Terraform resource.

### Remote State (Recommended for Production)

Configure a remote backend in your Terraform code:

```hcl
terraform {
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "vault/terraform.tfstate"
    region = "us-east-1"
  }
}
```

Or use Kubernetes backend:

```hcl
terraform {
  backend "kubernetes" {
    secret_suffix    = "vault-state"
    in_cluster_config = true
    namespace        = "flux-system"
  }
}
```

## Monitoring

### Check Terraform Resource Status

```bash
kubectl get terraform -A
kubectl describe terraform vault-config -n flux-system
```

### View Terraform Logs

```bash
# Controller logs
kubectl logs -n flux-system -l app.kubernetes.io/name=tf-controller --follow

# Runner pod logs (actual terraform execution)
kubectl logs -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config --follow
```

### View Plan Output

Plans are stored in the resource status:

```bash
kubectl get terraform vault-config -n flux-system -o yaml | grep -A 50 status
```

### Check Outputs

If using `writeOutputsToSecret`:

```bash
kubectl get secret vault-terraform-outputs -n flux-system -o jsonpath='{.data}' | jq
```

## Manual Plan Approval

For sensitive changes, use `approvePlan: plan-only`:

```yaml
spec:
  approvePlan: plan-only
```

Then manually approve:

```bash
# View the plan
kubectl describe terraform vault-config -n flux-system

# Approve and apply
kubectl annotate terraform vault-config \
  -n flux-system \
  infra.contrib.fluxcd.io/apply=true
```

## Drift Detection

tf-controller continuously checks for drift based on the `interval`. When drift is detected:

1. A new plan is generated
2. If `approvePlan: auto`, changes are applied automatically
3. If `approvePlan: plan-only`, you must manually approve

## Branch Planner (PR Automation)

Enable branch planner to get automatic plan comments on PRs:

```yaml
# In tf-controller HelmRelease
branchPlanner:
  enabled: true
```

This will:
- Comment terraform plans on pull requests
- Show what will change before merging
- Requires GitHub token/webhook setup

## Security Best Practices

1. **Sensitive Variables**: Always use Secrets, never commit tokens
   ```yaml
   varsFrom:
     - kind: Secret
       name: terraform-secrets
   ```

2. **RBAC**: Limit who can create/modify Terraform resources

3. **State Encryption**: Use encrypted remote backends

4. **Manual Approval**: Use `plan-only` for critical infrastructure

5. **Resource Limits**: Set appropriate limits on runner pods
   ```yaml
   runnerPodTemplate:
     spec:
       containers:
         - name: tf-runner
           resources:
             limits:
               memory: 1Gi
               cpu: 1000m
   ```

## Troubleshooting

### Terraform keeps failing

Check the runner pod logs:
```bash
kubectl logs -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config
```

### State locked

If state gets locked:
```bash
# Find the runner pod
kubectl get pods -n flux-system -l infra.contrib.fluxcd.io/terraform=vault-config

# Force unlock (if safe)
kubectl exec -it <runner-pod> -n flux-system -- terraform force-unlock <lock-id>
```

### Resource not reconciling

```bash
# Check controller logs
kubectl logs -n flux-system -l app.kubernetes.io/name=tf-controller

# Force reconciliation
flux reconcile source git flux-system
kubectl annotate terraform vault-config -n flux-system reconcile.fluxcd.io/requestedAt="$(date +%s)"
```

### Provider authentication issues

Ensure credentials are properly configured:
- For Vault: Provide VAULT_ADDR and VAULT_TOKEN via varsFrom
- For cloud providers: Use workload identity or service account keys

## Advanced: Multi-Environment

Create overlays for different environments:

```
infrastructure/
├── base/
│   └── terraform/
│       └── main.tf
└── overlays/
    ├── dev/
    │   └── terraform-dev.yaml
    ├── staging/
    │   └── terraform-staging.yaml
    └── prod/
        └── terraform-prod.yaml
```

Each overlay references the same Terraform code but with different variables.

## Migration to GitLab CI (Future)

When you add GitLab CI later, you can:

1. Keep tf-controller for automatic reconciliation
2. Use GitLab CI for planned changes
3. Or migrate entirely to GitLab CI and remove tf-controller

The Terraform code remains the same - just the execution method changes.

## Resources

- [tf-controller Documentation](https://weaveworks.github.io/tf-controller/)
- [GitHub Repository](https://github.com/weaveworks/tf-controller)
- [Terraform Resource API](https://weaveworks.github.io/tf-controller/References/terraform/)
- [Examples](https://github.com/weaveworks/tf-controller/tree/main/docs/use-cases)
