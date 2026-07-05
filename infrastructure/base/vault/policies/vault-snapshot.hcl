# Raft snapshot access for the nightly backup CronJob (Phase 2).
# Applied by bootstrap/vault-init.sh.
path "sys/storage/raft/snapshot" {
  capabilities = ["read"]
}
