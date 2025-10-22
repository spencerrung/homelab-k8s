# Podinfo Example Application

This is an example application to demonstrate how to deploy apps with Flux and Helm.

[Podinfo](https://github.com/stefanprodan/podinfo) is a tiny web application made with Go that showcases best practices of running microservices in Kubernetes.

## What's included

- **namespace.yaml**: Creates the podinfo namespace
- **repository.yaml**: Defines the Helm repository source
- **release.yaml**: Defines the HelmRelease with configuration values
- **kustomization.yaml**: Ties everything together

## Customization

To customize for your environment, create patches in `apps/overlays/homelab/` or modify the values in `release.yaml`.

## Removal

To remove this example once you've added your own apps:
1. Delete the `apps/base/podinfo/` directory
2. Remove the reference from `apps/base/kustomization.yaml`
3. Commit and push
