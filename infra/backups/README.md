# Database Backups

`infra/backups` owns the S3 bucket, upload-only IAM identity, retention policy, Object Lock configuration, and budget alerts for Goalkeepr database backups.

The state is stored at `goalkeepr/backups/terraform.tfstate` in the shared Terraform state bucket.

## Apply Backup Infrastructure

Run Terraform from this directory with AWS credentials and `TF_VAR_billing_alert_email` configured:

```console
terraform init
terraform apply
```

## Create the Kubernetes Secret

Extract the sensitive Terraform outputs and create the `goalkeepr-backup` Secret in Nushell:

```nu
let bucket = (terraform output -raw bucket_name); let access_key_id = (terraform output -raw access_key_id); let secret_access_key = (terraform output -raw secret_access_key); kubectl --namespace goalkeepr create secret generic goalkeepr-backup $"--from-literal=bucket=($bucket)" $"--from-literal=access_key_id=($access_key_id)" $"--from-literal=secret_access_key=($secret_access_key)" --dry-run=client --output=yaml | kubectl apply --filename=-
```

The backup CronJob will move into `infra/deployment` with the rest of the Kubernetes deployment configuration.

## Restore a Backup

Download the required archive from the `goalkeepr/` S3 prefix using an AWS identity that can read the bucket.
Restore it into an isolated PostgreSQL database before considering a production restore.

```console
createdb goalkeepr-restore
pg_restore --clean --if-exists --no-owner --dbname=goalkeepr-restore backup.dump
```

Verify the restored Goalkeepr data before replacing any production data.
