variable "billing_alert_email" {
  description = "Email address receiving Goalkeepr backup budget alerts."
  type        = string
}

variable "image" {
  description = "Goalkeepr container image."
  type        = string
}

variable "hosts" {
  description = "Hostnames served by Goalkeepr."
  type        = list(string)
}
