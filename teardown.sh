#!/usr/bin/env bash
# Deletes the NAT Gateway, the Elastic IP, the network and the VPC (everything tagged lab=aws-vpc-three-tier). Run with: ./teardown.sh
set -u
aws sts get-caller-identity >/dev/null 2>&1 || { echo "No working AWS credentials." >&2; exit 1; }
L=aws-vpc-three-tier
for n in $(aws ec2 describe-nat-gateways --filter Name=tag:lab,Values=$L Name=state,Values=available,pending --query 'NatGateways[].NatGatewayId' --output text); do
  aws ec2 delete-nat-gateway --nat-gateway-id $n >/dev/null && echo "deleting NAT Gateway $n (takes a minute)"
  for _ in $(seq 1 40); do [ "$(aws ec2 describe-nat-gateways --nat-gateway-ids $n --query 'NatGateways[0].State' --output text)" = deleted ] && break; sleep 5; done
done
for a in $(aws ec2 describe-addresses --filters Name=tag:lab,Values=$L --query 'Addresses[].AllocationId' --output text); do aws ec2 release-address --allocation-id $a && echo "released Elastic IP $a"; done
for V in $(aws ec2 describe-vpcs --filters Name=tag:lab,Values=$L --query 'Vpcs[].VpcId' --output text); do
  E=$(aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=$V --query 'VpcEndpoints[].VpcEndpointId' --output text)
  [ -n "$E" ] && aws ec2 delete-vpc-endpoints --vpc-endpoint-ids $E >/dev/null 2>&1
  for _ in 1 2 3 4 5 6; do
    for g in $(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$V --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text); do aws ec2 delete-security-group --group-id $g >/dev/null 2>&1; done
    for a in $(aws ec2 describe-route-tables --filters Name=vpc-id,Values=$V --query 'RouteTables[].Associations[?!Main].RouteTableAssociationId' --output text); do aws ec2 disassociate-route-table --association-id $a >/dev/null 2>&1; done
    for r in $(aws ec2 describe-route-tables --filters Name=vpc-id,Values=$V --query 'RouteTables[?length(Associations[?Main])==`0`].RouteTableId' --output text); do aws ec2 delete-route-table --route-table-id $r >/dev/null 2>&1; done
    for a in $(aws ec2 describe-network-acls --filters Name=vpc-id,Values=$V --query 'NetworkAcls[?!IsDefault].Associations[].NetworkAclAssociationId' --output text); do :; done
    for s in $(aws ec2 describe-subnets --filters Name=vpc-id,Values=$V --query 'Subnets[].SubnetId' --output text); do aws ec2 delete-subnet --subnet-id $s >/dev/null 2>&1; done
    for n in $(aws ec2 describe-network-acls --filters Name=vpc-id,Values=$V --query 'NetworkAcls[?!IsDefault].NetworkAclId' --output text); do aws ec2 delete-network-acl --network-acl-id $n >/dev/null 2>&1; done
    for g in $(aws ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values=$V --query 'InternetGateways[].InternetGatewayId' --output text); do aws ec2 detach-internet-gateway --internet-gateway-id $g --vpc-id $V >/dev/null 2>&1; aws ec2 delete-internet-gateway --internet-gateway-id $g >/dev/null 2>&1; done
    aws ec2 delete-vpc --vpc-id $V >/dev/null 2>&1 && { echo "deleted VPC $V"; break; }
    sleep 10
  done
done
echo "Now run ./verify-teardown.sh"
