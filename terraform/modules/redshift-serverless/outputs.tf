output "namespace_name" {
  value = aws_redshiftserverless_namespace.main.namespace_name
}

output "workgroup_name" {
  value = aws_redshiftserverless_workgroup.main.workgroup_name
}

output "spectrum_role_arn" {
  value = aws_iam_role.spectrum.arn
}

output "endpoint" {
  value       = aws_redshiftserverless_workgroup.main.endpoint
  description = "JDBC/ODBC connection endpoint."
}
