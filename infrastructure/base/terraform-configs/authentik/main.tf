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

# GitLab OAuth2 Provider and Application are now managed by Authentik Blueprint
# See: infrastructure/base/authentik/gitlab-oidc-blueprint.yaml
#
# Terraform cannot properly manage property_mappings (scope mappings) due to
# provider limitations, so we use Authentik's native blueprint system instead.
#
# Commented out to prevent conflicts with blueprint management:

# resource "authentik_provider_oauth2" "gitlab" {
#   name               = "GitLab"
#   client_id          = "gitlab"
#   client_type        = "confidential"
#   authorization_flow = data.authentik_flow.default_authorization_flow.id
#   signing_key        = data.authentik_certificate_key_pair.default.id
#
#   redirect_uris = [
#     "https://code.alucard.dev/users/auth/openid_connect/callback"
#   ]
# }

# resource "authentik_application" "gitlab" {
#   name              = "GitLab"
#   slug              = "gitlab"
#   protocol_provider = authentik_provider_oauth2.gitlab.id
#   meta_launch_url   = "https://code.alucard.dev"
#   meta_description  = "GitLab CE - Git repository and CI/CD platform"
# }

# output "gitlab_client_id" {
#   value       = authentik_provider_oauth2.gitlab.client_id
#   description = "GitLab OAuth2 Client ID"
# }

# output "gitlab_client_secret" {
#   value       = authentik_provider_oauth2.gitlab.client_secret
#   description = "GitLab OAuth2 Client Secret"
#   sensitive   = true
# }
