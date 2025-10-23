# Terraform Configurations

This directory contains Terraform resources that are applied AFTER the infrastructure layer is ready.

## Why Separate?

Terraform resources require the tf-controller CRDs to be installed first. By separating them into their own kustomization with a dependency on the infrastructure kustomization, we ensure:

1. tf-controller is deployed first (via infrastructure kustomization)
2. CRDs are available
3. Then Terraform resources can be applied (via terraform-configs kustomization)

## Structure

```
terraform-configs/
├── terraform-vault-config.yaml    # Vault configuration via Terraform
└── kustomization.yaml             # References all Terraform resources
```

## Adding New Terraform Resources

When adding new Terraform configurations:

1. Create the Terraform code in the appropriate component directory:
   ```
   infrastructure/base/mycomponent/terraform/
   ```

2. Create a Terraform resource YAML:
   ```yaml
   apiVersion: infra.contrib.fluxcd.io/v1alpha2
   kind: Terraform
   metadata:
     name: mycomponent
     namespace: flux-system
   spec:
     # ... configuration
   ```

3. Add it to this kustomization:
   ```bash
   # Add to terraform-configs/kustomization.yaml
   resources:
     - terraform-vault-config.yaml
     - terraform-mycomponent.yaml  # Add this
   ```

4. Commit and push - Flux will apply it automatically after infrastructure is ready

## Deployment Order

```
1. infrastructure kustomization deploys:
   - sources (Helm repositories)
   - tf-controller
   - vault
   - external-secrets

2. terraform-configs kustomization deploys (after infrastructure):
   - Terraform resources that configure infrastructure

3. apps kustomization deploys (after infrastructure):
   - Application workloads
```

This ensures proper dependency ordering!
