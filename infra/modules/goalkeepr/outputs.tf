output "backup_bucket_name" {
  description = "S3 bucket receiving Goalkeepr database backups."
  value       = module.bucket.s3_bucket_id
}

output "backup_access_key_id" {
  description = "Access key ID for the Goalkeepr backup Kubernetes Secret."
  value       = module.upload_user.access_key_id
  sensitive   = true
}

output "backup_secret_access_key" {
  description = "Secret access key for the Goalkeepr backup Kubernetes Secret."
  value       = module.upload_user.access_key_secret
  sensitive   = true
}
