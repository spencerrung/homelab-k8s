# 3. Traefik as NodePort behind an external reverse proxy

Accepted 2025-10.

Bare-metal cluster with no LoadBalancer implementation: a Service of type
LoadBalancer would never get an IP. Instead of MetalLB, an external
reverse proxy (already present on the network edge) forwards to Traefik's
NodePorts, and Cloudflare fronts public hostnames. Certificates are
issued in-cluster via DNS-01 (no inbound challenge path needed), so the
proxy stays a dumb forwarder. Cost: one extra hop and per-hostname route
maintenance on the proxy — documented in the add-an-app runbook.
