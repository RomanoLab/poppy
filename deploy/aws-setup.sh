#!/bin/bash
# Provision the POPPy web server on the UPenn-managed AWS account.
# Run from CloudShell, from inside the repo root:  bash deploy/aws-setup.sh
# Idempotent-ish: reuses an existing key pair / security group if present.
set -euo pipefail

export AWS_DEFAULT_REGION=us-east-1
NAME=poppy-web
KEY=${NAME}-key
SG_NAME=${NAME}-sg
INSTANCE_TYPE=${INSTANCE_TYPE:-t3.small}   # override with: INSTANCE_TYPE=t3.micro bash deploy/aws-setup.sh

echo "== Resolving latest Ubuntu 24.04 LTS AMI =="
AMI=$(aws ssm get-parameter \
  --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query 'Parameter.Value' --output text)
echo "AMI=$AMI"

echo "== Finding the internet-facing VPC =="
VPC=$(aws ec2 describe-internet-gateways \
  --query 'InternetGateways[0].Attachments[0].VpcId' --output text)
echo "VPC=$VPC"

echo "== Finding a public subnet (route 0.0.0.0/0 -> igw) =="
PUB_SUBNET=""
for st in $(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC \
              --query 'Subnets[].SubnetId' --output text); do
  rt=$(aws ec2 describe-route-tables --filters Name=association.subnet-id,Values=$st \
        --query 'RouteTables[0].RouteTableId' --output text)
  if [ "$rt" = "None" ] || [ -z "$rt" ]; then
    rt=$(aws ec2 describe-route-tables \
          --filters Name=vpc-id,Values=$VPC Name=association.main,Values=true \
          --query 'RouteTables[0].RouteTableId' --output text)
  fi
  igw=$(aws ec2 describe-route-tables --route-table-ids $rt \
        --query "RouteTables[0].Routes[?starts_with(GatewayId, 'igw-')].GatewayId | [0]" \
        --output text)
  if [ "$igw" != "None" ] && [ -n "$igw" ]; then PUB_SUBNET=$st; break; fi
done
[ -n "$PUB_SUBNET" ] || { echo "ERROR: no public subnet found in $VPC"; exit 1; }
echo "PUB_SUBNET=$PUB_SUBNET"

echo "== SSH key pair =="
if ! aws ec2 describe-key-pairs --key-names $KEY >/dev/null 2>&1; then
  aws ec2 create-key-pair --key-name $KEY --query 'KeyMaterial' --output text > ~/${KEY}.pem
  chmod 600 ~/${KEY}.pem
  echo "created ~/${KEY}.pem"
else
  echo "reusing existing key pair $KEY"
fi

echo "== Security group =="
SG=$(aws ec2 describe-security-groups \
      --filters Name=group-name,Values=$SG_NAME Name=vpc-id,Values=$VPC \
      --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)
if [ "$SG" = "None" ] || [ -z "$SG" ]; then
  SG=$(aws ec2 create-security-group --group-name $SG_NAME \
        --description "POPPy web server" --vpc-id $VPC --query 'GroupId' --output text)
  echo "created $SG"
else
  echo "reusing $SG"
fi
MYIP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 22  --cidr ${MYIP}/32 2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 80  --cidr 0.0.0.0/0   2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 443 --cidr 0.0.0.0/0   2>/dev/null || true
echo "SG=$SG (ssh allowed from ${MYIP}/32)"

echo "== Launching instance ($INSTANCE_TYPE) =="
IID=$(aws ec2 run-instances \
  --image-id $AMI \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY \
  --subnet-id $PUB_SUBNET \
  --security-group-ids $SG \
  --associate-public-ip-address \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' \
  --user-data file://deploy/user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=poppy-web}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "INSTANCE=$IID  (waiting for running state...)"
aws ec2 wait instance-running --instance-ids $IID
PUBIP=$(aws ec2 describe-instances --instance-ids $IID \
        --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

cat > ~/poppy-env.sh <<EOF
export AWS_DEFAULT_REGION=us-east-1
export NAME=$NAME KEY=$KEY SG=$SG VPC=$VPC SUBNET=$PUB_SUBNET
export INSTANCE=$IID
export PUBIP=$PUBIP
EOF

echo ""
echo "=================================================================="
echo "  Instance:    $IID"
echo "  Public IP:   $PUBIP"
echo "  SSH:         ssh -i ~/${KEY}.pem ubuntu@$PUBIP"
echo ""
echo "  NEXT: point poppyontology.org DNS at this IP:"
echo "     A   @     $PUBIP"
echo "     A   www   $PUBIP"
echo ""
echo "  The site finishes installing ~2-3 min after launch (cloud-init)."
echo "  Test:  curl -I http://$PUBIP/   (expect HTTP 200 once ready)"
echo "=================================================================="
