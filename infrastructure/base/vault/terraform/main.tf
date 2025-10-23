terraform {
  required_version = ">= 1.0"

  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "~> 4.0"
    }
  }
}

provider "vault" {
  # Address will be configured via environment variable or Terraform resource
  # VAULT_ADDR and VAULT_TOKEN will be provided by the Terraform resource
  address = var.vault_address
  token   = var.vault_token

  # Skip TLS verification for internal cluster communication
  skip_tls_verify = true
}

variable "vault_address" {
  description = "Vault server address"
  type        = string
  default     = "http://vault.vault.svc.cluster.local:8200"
}

variable "vault_token" {
  description = "Vault root or admin token"
  type        = string
  sensitive   = true
}

# KV v2 secrets engine already exists in dev mode at secret/
# We'll just use the existing mount instead of trying to create it
# Reference the existing mount path directly in resources below

# Enable Kubernetes auth method
resource "vault_auth_backend" "kubernetes" {
  type = "kubernetes"
  path = "kubernetes"
}

# Configure Kubernetes auth backend
resource "vault_kubernetes_auth_backend_config" "kubernetes" {
  backend            = vault_auth_backend.kubernetes.path
  kubernetes_host    = "https://kubernetes.default.svc.cluster.local:443"
  disable_local_ca_jwt = false
}

# Policy for External Secrets Operator
resource "vault_policy" "external_secrets" {
  name = "external-secrets"

  policy = <<EOT
# Read secrets from KV v2
path "secret/data/*" {
  capabilities = ["read", "list"]
}

# List secrets metadata
path "secret/metadata/*" {
  capabilities = ["list"]
}
EOT
}

# Kubernetes auth role for External Secrets Operator
resource "vault_kubernetes_auth_backend_role" "external_secrets" {
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "external-secrets"
  bound_service_account_names      = ["external-secrets-sa"]
  bound_service_account_namespaces = ["*"]
  token_ttl                        = 3600
  token_policies                   = [vault_policy.external_secrets.name]
}

# Example: Create a test secret
resource "vault_kv_secret_v2" "test" {
  mount               = "secret"  # Use existing mount path
  name                = "test"
  cas                 = 1
  delete_all_versions = true

  data_json = jsonencode({
    username = "testuser"
    password = "changeme"
  })
}

# Authentik PostgreSQL credentials
resource "vault_kv_secret_v2" "authentik_postgresql" {
  mount               = "secret"
  name                = "authentik/postgresql"
  cas                 = 1
  delete_all_versions = true

  data_json = jsonencode({
    username = "authentik"
    password = "authentik-secure-password-change-me"  # Change this!
  })
}

# Authentik secret key for sessions
resource "vault_kv_secret_v2" "authentik_secret_key" {
  mount               = "secret"
  name                = "authentik/secret-key"
  cas                 = 1
  delete_all_versions = true

  data_json = jsonencode({
    secret_key = "change-me-to-a-random-50-char-string-for-production"
  })
}

# Cloudflare API token for cert-manager DNS-01 challenges
# NOTE: This secret should be created manually to avoid storing the token in Git:
# kubectl exec -n vault vault-0 -- vault kv put secret/cert-manager/cloudflare api-token="YOUR_TOKEN_HERE"

# Authentik API token for Terraform automation
# NOTE: Create this manually after Authentik is running:
# kubectl exec -n vault vault-0 -- vault kv put secret/authentik/terraform-token api-token="YOUR_AUTHENTIK_API_TOKEN_HERE"

# Output useful information
output "kv_mount_path" {
  value       = "secret"
  description = "Path where KV v2 secrets engine is mounted"
}

output "kubernetes_auth_path" {
  value       = vault_auth_backend.kubernetes.path
  description = "Path where Kubernetes auth is mounted"
}

output "external_secrets_role" {
  value       = vault_kubernetes_auth_backend_role.external_secrets.role_name
  description = "Kubernetes auth role for External Secrets Operator"
}
