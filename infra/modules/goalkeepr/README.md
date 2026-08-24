# Goalkeepr Infrastructure Template

This module owns Goalkeepr's AWS backup storage and Kubernetes deployment resources.
The backup bucket retains archives for 90 days with Object Lock governance retention.
The upload identity can upload archives but cannot read or delete them.

The PostgreSQL data PVC has `prevent_destroy` enabled to protect production data.

## Restore A Backup

Download the required archive from the `goalkeepr/` S3 prefix using an AWS identity that can read the bucket.
Restore it into an isolated PostgreSQL database before considering a production restore.

```console
createdb goalkeepr-restore
pg_restore --clean --if-exists --no-owner --dbname=goalkeepr-restore backup.dump
```

Verify the restored Goalkeepr data before replacing any production data.
