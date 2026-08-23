# Infrastructure

`modules/goalkeepr` defines the complete Goalkeepr infrastructure template.
`envs/mhemeryck/goalkeepr` instantiates it for the home environment.

The environment state is stored at `goalkeepr/terraform.tfstate` in the shared Terraform state bucket.
