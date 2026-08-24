resource "random_password" "postgres_password" {
  length  = 64
  special = false
}

resource "kubernetes_secret_v1" "postgres" {
  wait_for_service_account_token = false

  metadata {
    name      = "postgres"
    namespace = "goalkeepr"
  }

  data = {
    password = random_password.postgres_password.result
    username = "goalkeepr"
  }

  type = "Opaque"
}

resource "kubernetes_persistent_volume_claim_v1" "postgres_data" {
  metadata {
    name      = "postgres-pgdata"
    namespace = "goalkeepr"
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "local-path"
    volume_mode        = "Filesystem"

    resources {
      requests = {
        storage = "1Gi"
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "kubernetes_stateful_set_v1" "postgres" {
  depends_on = [kubernetes_secret_v1.postgres]

  wait_for_rollout = false

  metadata {
    name      = "postgres"
    namespace = "goalkeepr"
  }

  spec {
    service_name = "postgres"
    replicas     = 1

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    persistent_volume_claim_retention_policy {
      when_deleted = "Retain"
      when_scaled  = "Retain"
    }

    template {
      metadata {
        labels = {
          app = "postgres"
        }

        annotations = {
          "goalkeepr.app/postgres-secret-generation" = "1"
        }
      }

      spec {
        automount_service_account_token = false
        enable_service_links            = false

        container {
          name  = "postgres"
          image = "postgres:18-alpine"

          env {
            name  = "POSTGRES_DB"
            value = "goalkeepr"
          }

          env {
            name = "POSTGRES_PASSWORD"

            value_from {
              secret_key_ref {
                name = "postgres"
                key  = "password"
              }
            }
          }

          env {
            name = "POSTGRES_USER"

            value_from {
              secret_key_ref {
                name = "postgres"
                key  = "username"
              }
            }
          }

          port {
            container_port = 5432
          }

          resources {
            limits = {
              memory = "512Mi"
            }
          }

          volume_mount {
            name       = "pgdata"
            mount_path = "/var/lib/postgresql"
          }
        }

        volume {
          name = "pgdata"

          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.postgres_data.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "postgres" {
  wait_for_load_balancer = false

  metadata {
    name      = "postgres"
    namespace = "goalkeepr"
  }

  spec {
    selector = {
      app = "postgres"
    }

    port {
      port        = 5432
      target_port = 5432
    }
  }
}
