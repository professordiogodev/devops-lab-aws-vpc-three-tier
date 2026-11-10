#!/usr/bin/env bash
# Proves the lab left nothing in AWS. Run with: ./verify-teardown.sh
set -u
ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "No working AWS credentials." >&2; exit 1; }
echo "Checking account $ACCOUNT, region $(aws configure get region)"
pass=0; failn=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS  $d"; pass=$((pass+1)); else echo "FAIL  $d"; failn=$((failn+1)); fi; }
empty() { local r; r=$(eval "$1" 2>/dev/null); [ -z "$r" ] || [ "$r" = None ]; }
T="Name=tag:lab,Values=aws-vpc-three-tier"
check "no VPC tagged lab=aws-vpc-three-tier" empty "aws ec2 describe-vpcs --filters $T --query 'Vpcs[].VpcId' --output text"
check "no NAT Gateway tagged lab=aws-vpc-three-tier (it bills every hour)" empty "aws ec2 describe-nat-gateways --filter $T Name=state,Values=pending,available,deleting --query 'NatGateways[].NatGatewayId' --output text"
check "no Elastic IP tagged lab=aws-vpc-three-tier" empty "aws ec2 describe-addresses --filters $T --query 'Addresses[].PublicIp' --output text"
check "no internet gateway, subnet or security group tagged lab=aws-vpc-three-tier" empty "aws ec2 describe-internet-gateways --filters $T --query 'InternetGateways[].InternetGatewayId' --output text; aws ec2 describe-subnets --filters $T --query 'Subnets[].SubnetId' --output text; aws ec2 describe-security-groups --filters $T --query 'SecurityGroups[].GroupId' --output text"
echo
if [ "$failn" -eq 0 ]; then echo "TEARDOWN VERIFIED ($pass/$pass) in account $ACCOUNT"; else echo "NOT CLEAN: $failn leftover(s). Remove them and run this again."; fi
exit "$failn"
