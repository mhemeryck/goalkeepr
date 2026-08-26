data "aws_caller_identity" "current" {}

locals {
  bucket_name = "goalkeepr-backups-${data.aws_caller_identity.current.account_id}"
}

module "bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 5.15"

  bucket = local.bucket_name

  force_destroy            = false
  control_object_ownership = true
  object_ownership         = "BucketOwnerEnforced"

  versioning = {
    enabled = true
  }

  object_lock_enabled = true
  object_lock_configuration = {
    rule = {
      default_retention = {
        mode = "GOVERNANCE"
        days = 90
      }
    }
  }

  lifecycle_rule = [
    {
      id      = "expire-backups-after-retention"
      enabled = true

      expiration = {
        days = 90
      }

      noncurrent_version_expiration = {
        days = 1
      }
    },
  ]

  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
    }
  }

  attach_deny_insecure_transport_policy = true

  tags = {
    Application = "goalkeepr"
    Purpose     = "database-backups"
  }
}

module "upload_policy" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-policy"
  version = "~> 6.8"

  name        = "goalkeepr-backup-upload"
  description = "Upload Goalkeepr PostgreSQL backups without reading or deleting them."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:ListBucketMultipartUploads",
        ]
        Resource = module.bucket.s3_bucket_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts",
          "s3:PutObject",
        ]
        Resource = "${module.bucket.s3_bucket_arn}/goalkeepr/*"
      },
    ]
  })
}

module "upload_user" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-user"
  version = "~> 6.8"

  name                 = "goalkeepr-backup"
  create_access_key    = true
  create_login_profile = false
  force_destroy        = false
  policies = {
    upload = module.upload_policy.arn
  }
}

resource "kubernetes_secret_v1" "backup" {
  wait_for_service_account_token = false

  metadata {
    name      = "goalkeepr-backup"
    namespace = "goalkeepr"
  }

  data = {
    access_key_id     = module.upload_user.access_key_id
    bucket            = module.bucket.s3_bucket_id
    secret_access_key = module.upload_user.access_key_secret
  }

  type = "Opaque"
}

resource "aws_budgets_budget" "monthly_cost" {
  name         = "goalkeepr-backups"
  budget_type  = "COST"
  limit_amount = "5"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    notification_type          = "ACTUAL"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.billing_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    notification_type          = "FORECASTED"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.billing_alert_email]
  }
}

resource "kubernetes_cron_job_v1" "postgres_backup" {
  depends_on = [kubernetes_secret_v1.postgres]

  metadata {
    name        = "postgres-backup"
    namespace   = "goalkeepr"
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
        parallelism   = 1

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
                    name     = "postgres"
                    key      = "password"
                    optional = false
                  }
                }
              }

              env {
                name = "PGUSER"

                value_from {
                  secret_key_ref {
                    name     = "postgres"
                    key      = "username"
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
                    name     = "goalkeepr-backup"
                    key      = "access_key_id"
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
                    name     = "goalkeepr-backup"
                    key      = "secret_access_key"
                    optional = false
                  }
                }
              }

              env {
                name = "S3_BUCKET"

                value_from {
                  secret_key_ref {
                    name     = "goalkeepr-backup"
                    key      = "bucket"
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
    # The provider renders Kubernetes' omitted completion default as zero.
    ignore_changes = [spec[0].job_template[0].spec[0].completions]
  }
}
