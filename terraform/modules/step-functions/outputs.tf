output "state_machine_arn" {
  value = aws_sfn_state_machine.orders_medallion.arn
}

output "state_machine_name" {
  value = aws_sfn_state_machine.orders_medallion.name
}

output "execution_role_arn" {
  value = aws_iam_role.sfn_execution.arn
}
