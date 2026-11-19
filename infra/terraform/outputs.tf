output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "public_subnets" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "database_endpoint" {
  description = "RDS endpoint"
  value       = module.database.endpoint
}

output "database_port" {
  description = "RDS port"
  value       = module.database.port
}

output "redis_endpoint" {
  description = "ElastiCache endpoint"
  value       = module.redis.endpoint
}

output "documents_bucket_arn" {
  description = "Documents S3 bucket ARN"
  value       = module.storage.documents_bucket_arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.compute.ecs_cluster_name
}

output "alb_dns_name" {
  description = "Load balancer DNS name"
  value       = module.compute.alb_dns_name
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = module.cdn.domain_name
}

output "api_service_url" {
  description = "API service URL"
  value       = "https://${module.cdn.domain_name}/api"
}

output "web_service_url" {
  description = "Web service URL"
  value       = "https://${module.cdn.domain_name}/"
}