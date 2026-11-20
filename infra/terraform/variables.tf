# Environment
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "domain_name" {
  description = "Primary domain name"
  type        = string
  default     = "b2b.microsaas.com"
}

variable "admin_email" {
  description = "Admin email for production"
  type        = string
  default     = "admin@b2b.microsaas.com"
}

# VPC
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "List of private subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnet_cidrs" {
  description = "List of public subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

# Database
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "b2b"
}

variable "db_allocated_storage" {
  description = "DB allocated storage in GB"
  type        = number
  default     = 20
}

# Redis
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

# S3
variable "documents_bucket_name" {
  description = "S3 bucket name for documents"
  type        = string
  default     = "b2b-production-documents"
}

# ECS
variable "api_cpu" {
  description = "API service CPU units"
  type        = number
  default     = 1024
}

variable "api_memory" {
  description = "API service memory (MB)"
  type        = number
  default     = 2048
}

variable "worker_cpu" {
  description = "Worker service CPU units"
  type        = number
  default     = 1024
}

variable "worker_memory" {
  description = "Worker service memory (MB)"
  type        = number
  default     = 2048
}

# R Service
variable "r_cpu" {
  description = "R service CPU units"
  type        = number
  default     = 1024
}

variable "r_memory" {
  description = "R service memory (MB)"
  type        = number
  default     = 2048
}

# R Service Worker CPU
variable "r_worker_cpu" {
  description = "R worker service CPU units"
  type        = number
  default     = 1024
}

variable "r_worker_memory" {
  description = "R worker service memory (MB)"
  type        = number
  default     = 2048
}

# Billing
variable "stripe_webhook_url" {
  description = "Stripe webhook URL"
  type        = string
  default     = ""
}

variable "razorpay_webhook_url" {
  description = "Razorpay webhook URL"
  type        = string
  default     = ""
}

# Email
variable "email_from" {
  description = "Email sender address"
  type        = string
  default     = "noreply@b2b.microsaas.com"
}

# Monitoring
variable "slack_alerts_channel" {
  description = "Slack channel for alerts"
  type        = string
  default     = "#alerts"
}

variable "pagerduty_service_key" {
  description = "PagerDuty service key"
  type        = string
  default     = ""
  sensitive   = true
}