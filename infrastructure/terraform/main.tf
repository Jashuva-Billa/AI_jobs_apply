terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

variable "environment" {
  default = "production"
}

# S3 Bucket for Resume & Tailored Application Storage
resource "aws_s3_bucket" "resumes" {
  bucket = "agentic-jobs-resumes-${var.environment}"
}

# ECS Cluster for Backend & Multi-Agent Services
resource "aws_ecs_cluster" "app_cluster" {
  name = "agentic-jobs-cluster-${var.environment}"
}

# Security Group for Backend API
resource "aws_security_group" "api_sg" {
  name        = "agentic-jobs-api-sg"
  description = "Allow inbound HTTP/HTTPS traffic"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
