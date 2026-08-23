resource "kubernetes_deployment_v1" "goalkeepr" {
  wait_for_rollout = false

  metadata {
    name      = "goalkeepr"
    namespace = "goalkeepr"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "goalkeepr"
      }
    }

    strategy {
      type = "RollingUpdate"

      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    template {
      metadata {
        labels = {
          app = "goalkeepr"
        }
      }

      spec {
        automount_service_account_token = false
        enable_service_links            = false

        container {
          name    = "goalkeepr"
          image   = var.image
          command = ["sh", "-c", "python manage.py migrate && uvicorn goalkeepr.asgi:application --host 0.0.0.0 --port 8000"]

          env {
            name  = "DJANGO_ALLOWED_HOSTS"
            value = local.allowed_hosts
          }

          env {
            name  = "DJANGO_CSRF_TRUSTED_ORIGINS"
            value = local.csrf_trusted_origins
          }

          env {
            name  = "DJANGO_DEBUG"
            value = "false"
          }

          env {
            name = "DJANGO_SECRET_KEY"

            value_from {
              secret_key_ref {
                name = "goalkeepr"
                key  = "secret_key"
              }
            }
          }

          env {
            name  = "POSTGRES_DB"
            value = "goalkeepr"
          }

          env {
            name  = "POSTGRES_HOST"
            value = "postgres"
          }

          env {
            name  = "POSTGRES_PORT"
            value = "5432"
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

          env {
            name  = "TEAM_NAME"
            value = "K.F.C. Sparta Kolmont"
          }

          port {
            container_port = 8000
          }

          readiness_probe {
            http_get {
              path = "/healthz/"
              port = 8000

              http_header {
                name  = "Host"
                value = local.readiness_host
              }
            }

            period_seconds = 5
            timeout_seconds = 2
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "goalkeepr" {
  wait_for_load_balancer = false

  metadata {
    name      = "goalkeepr"
    namespace = "goalkeepr"
  }

  spec {
    selector = {
      app = "goalkeepr"
    }

    port {
      port        = 80
      target_port = 8000
    }
  }
}

resource "kubernetes_ingress_v1" "goalkeepr" {
  metadata {
    name      = "goalkeepr"
    namespace = "goalkeepr"

    annotations = {
      "cert-manager.io/cluster-issuer" = "letsencrypt"
    }
  }

  spec {
    ingress_class_name = "traefik"

    tls {
      hosts       = var.hosts
      secret_name = "goalkeepr-mhemeryck-xyz-tls"
    }

    dynamic "rule" {
      for_each = var.hosts

      content {
        host = rule.value

        http {
          path {
            path_type = "ImplementationSpecific"

            backend {
              service {
                name = "goalkeepr"

                port {
                  number = 80
                }
              }
            }
          }
        }
      }
    }
  }
}
