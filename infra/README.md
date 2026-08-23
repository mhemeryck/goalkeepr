# Infrastructure

Each Terraform root has an independent remote state and owns one Goalkeepr responsibility.

`backups` owns the AWS database-backup storage and upload identity.
`deployment` will own the Kubernetes application deployment.
