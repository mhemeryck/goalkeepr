locals {
  allowed_hosts        = join(",", var.hosts)
  csrf_trusted_origins = join(",", [for host in var.hosts : "https://${host}"])
  readiness_host       = var.hosts[0]
}
