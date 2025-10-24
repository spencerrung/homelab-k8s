terraform {
  required_version = ">= 1.0"

  required_providers {
    authentik = {
      source  = "goauthentik/authentik"
      version = "~> 2024.8.0"
    }
  }
}

provider "authentik" {
  url   = var.authentik_url
  token = var.authentik_token
}

variable "authentik_url" {
  description = "Authentik server URL"
  type        = string
  default     = "https://auth.alucard.dev"
}

variable "authentik_token" {
  description = "Authentik API token"
  type        = string
  sensitive   = true
}

# Get the default authorization flow
data "authentik_flow" "default_authorization_flow" {
  slug = "default-provider-authorization-implicit-consent"
}

# Get default certificate
data "authentik_certificate_key_pair" "default" {
  name = "authentik Self-signed Certificate"
}

# Create OAuth2 Provider for GitLab
resource "authentik_provider_oauth2" "gitlab" {
  name               = "GitLab"
  client_id          = "gitlab"
  client_type        = "confidential"
  authorization_flow = data.authentik_flow.default_authorization_flow.id
  signing_key        = data.authentik_certificate_key_pair.default.id

  redirect_uris = [
    "https://code.alucard.dev/users/auth/openid_connect/callback"
  ]

  # Note: property_mappings (scope mappings) must be configured manually in Authentik UI
  # Terraform cannot manage them due to provider limitations with data sources
  # By omitting this field entirely, Terraform will ignore drift in this attribute
}

# Create Application
resource "authentik_application" "gitlab" {
  name              = "GitLab"
  slug              = "gitlab"
  protocol_provider = authentik_provider_oauth2.gitlab.id
  meta_launch_url   = "https://code.alucard.dev"
  meta_description  = "GitLab CE - Git repository and CI/CD platform"
}

# Output the client secret (will be stored in Terraform state)
output "gitlab_client_id" {
  value       = authentik_provider_oauth2.gitlab.client_id
  description = "GitLab OAuth2 Client ID"
}

output "gitlab_client_secret" {
  value       = authentik_provider_oauth2.gitlab.client_secret
  description = "GitLab OAuth2 Client Secret"
  sensitive   = true
}
