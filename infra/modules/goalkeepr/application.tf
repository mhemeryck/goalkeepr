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
            value = "goalkeepr.mhemeryck.xyz,goalkeepr.app"
          }

          env {
            name  = "DJANGO_CSRF_TRUSTED_ORIGINS"
            value = "https://goalkeepr.mhemeryck.xyz,https://goalkeepr.app"
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
                value = "goalkeepr.mhemeryck.xyz"
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

resource "kubernetes_cron_job_v1" "postgres_backup" {
  metadata {
    name      = "postgres-backup"
    namespace = "goalkeepr"
    annotations = {}
    labels      = {}
  }

  spec {
    schedule                      = "0 2 * * *"
    concurrency_policy            = "Forbid"
    failed_jobs_history_limit     = 7
    successful_jobs_history_limit = 7
    starting_deadline_seconds     = 3600

    job_template {
      metadata {
        annotations = {}
        labels      = {}
      }

      spec {
        backoff_limit = 2

        template {
          metadata {
            annotations = {}
            labels      = {}
          }

          spec {
            automount_service_account_token = false
            enable_service_links            = false
            restart_policy                  = "Never"

            volume {
              name = "backup"

              empty_dir {}
            }

            init_container {
              name    = "dump"
              image   = "postgres:18-alpine"
              command = ["/bin/sh", "-ceu", "pg_dump --format=custom --no-owner --no-privileges --file=/backup/goalkeepr.dump\npg_restore --list /backup/goalkeepr.dump >/dev/null\n"]

              security_context {
                allow_privilege_escalation = false
                run_as_non_root            = false
                run_as_user                = 0
              }

              env {
                name  = "PGDATABASE"
                value = "goalkeepr"
              }

              env {
                name  = "PGHOST"
                value = "postgres"
              }

              env {
                name = "PGPASSWORD"

                value_from {
                  secret_key_ref {
                    name = "postgres"
                    key  = "password"
                    optional = false
                  }
                }
              }

              env {
                name = "PGUSER"

                value_from {
                  secret_key_ref {
                    name = "postgres"
                    key  = "username"
                    optional = false
                  }
                }
              }

              volume_mount {
                name       = "backup"
                mount_path = "/backup"
              }

              resources {
                limits   = {}
                requests = {}
              }
            }

            container {
              name    = "upload"
              image   = "amazon/aws-cli:2.35.11"
              command = ["/bin/sh", "-ceu", "timestamp=\"$(date -u +%Y-%m-%dT%H-%M-%SZ)\"\naws s3 cp /backup/goalkeepr.dump \"s3://$${S3_BUCKET}/goalkeepr/$${timestamp}.dump\" --only-show-errors\n"]

              env {
                name = "AWS_ACCESS_KEY_ID"

                value_from {
                  secret_key_ref {
                    name = "goalkeepr-backup"
                    key  = "access_key_id"
                    optional = false
                  }
                }
              }

              env {
                name  = "AWS_DEFAULT_REGION"
                value = "eu-central-1"
              }

              env {
                name = "AWS_SECRET_ACCESS_KEY"

                value_from {
                  secret_key_ref {
                    name = "goalkeepr-backup"
                    key  = "secret_access_key"
                    optional = false
                  }
                }
              }

              env {
                name = "S3_BUCKET"

                value_from {
                  secret_key_ref {
                    name = "goalkeepr-backup"
                    key  = "bucket"
                    optional = false
                  }
                }
              }

              volume_mount {
                name       = "backup"
                mount_path = "/backup"
              }

              resources {
                limits   = {}
                requests = {}
              }
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      spec[0].job_template[0].spec[0].completions,
      spec[0].job_template[0].spec[0].parallelism,
    ]
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
      hosts       = ["goalkeepr.mhemeryck.xyz", "goalkeepr.app"]
      secret_name = "goalkeepr-mhemeryck-xyz-tls"
    }

    rule {
      host = "goalkeepr.mhemeryck.xyz"

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

    rule {
      host = "goalkeepr.app"

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
