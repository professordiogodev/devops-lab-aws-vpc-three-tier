#!/usr/bin/env python3
import ipaddress, json, os, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
passed = failed = 0


def check(desc, ok, hint=""):
    global passed, failed
    if ok:
        passed += 1; print("PASS  " + desc)
    else:
        failed += 1; print("FAIL  " + desc + (("   -> " + hint) if hint else ""))


def aws(*a):
    try:
        return json.loads(subprocess.check_output(("aws",) + a + ("--output", "json"), stderr=subprocess.DEVNULL, timeout=60) or "null")
    except Exception:
        return None


check("no AWS keys in the repository", subprocess.run("git grep -lE 'AKIA[0-9A-Z]{16}' -- . ':!.lab' ':!verify.sh'", shell=True, capture_output=True, text=True).stdout.strip() == "")
F = "Name=tag:lab,Values=aws-vpc-three-tier"
print("== The VPC and its six subnets ==")
vpcs = (aws("ec2", "describe-vpcs", "--filters", F) or {}).get("Vpcs", [])
check("exactly one VPC tagged lab=aws-vpc-three-tier, a /16 in private address space", len(vpcs) == 1 and vpcs[0]["CidrBlock"].endswith("/16") and ipaddress.ip_network(vpcs[0]["CidrBlock"]).is_private)
if len(vpcs) != 1:
    print("\nNothing else can be checked.\n%d check(s) failed, %d passed" % (failed, passed)); sys.exit(1)
vpc = vpcs[0]; V = vpc["VpcId"]; VF = "Name=vpc-id,Values=" + V
vnet = ipaddress.ip_network(vpc["CidrBlock"])
subs = (aws("ec2", "describe-subnets", "--filters", VF) or {}).get("Subnets", [])
tier = {"web": [], "app": [], "data": []}
for s in subs:
    t = next((x["Value"] for x in s.get("Tags", []) if x["Key"] == "Tier"), None)
    if t in tier:
        tier[t].append(s)
check("six subnets, two per tier, tagged Tier = web, app, data", len(subs) == 6 and all(len(v) == 2 for v in tier.values()), "found %s" % {k: len(v) for k, v in tier.items()})
check("each tier spans two different availability zones", all(len({s["AvailabilityZone"] for s in v}) == 2 for v in tier.values()))
nets = [ipaddress.ip_network(s["CidrBlock"]) for s in subs]
check("subnets are /24 to /26, inside the VPC and do not overlap",
      all(n.subnet_of(vnet) and 24 <= n.prefixlen <= 26 for n in nets) and not any(a.overlaps(b) for i, a in enumerate(nets) for b in nets[i + 1:]))
check("only the web subnets give servers a public IP automatically", all(s.get("MapPublicIpOnLaunch") for s in tier["web"]) and not any(s.get("MapPublicIpOnLaunch") for s in tier["app"] + tier["data"]))

print("== Routes: who can reach the internet ==")
rts = (aws("ec2", "describe-route-tables", "--filters", VF) or {}).get("RouteTables", [])
def default_route(subnet_id):
    rt = next((r for r in rts if any(a.get("SubnetId") == subnet_id for a in r["Associations"])), None)
    if rt is None:
        rt = next((r for r in rts if any(a.get("Main") for a in r["Associations"])), None)
    for r in (rt or {}).get("Routes", []):
        if r.get("DestinationCidrBlock") == "0.0.0.0/0" or r.get("DestinationIpv6CidrBlock") == "::/0":
            return "igw" if r.get("GatewayId", "").startswith("igw-") else "nat" if r.get("NatGatewayId") else "other"
    return None
check("web subnets: 0.0.0.0/0 goes to an internet gateway", all(default_route(s["SubnetId"]) == "igw" for s in tier["web"]))
check("app subnets: 0.0.0.0/0 goes to a NAT Gateway (out, not in)", all(default_route(s["SubnetId"]) == "nat" for s in tier["app"]))
check("data subnets: NO default route at all (no internet gateway, no NAT: not in either direction)", all(default_route(s["SubnetId"]) is None for s in tier["data"]))
nats = (aws("ec2", "describe-nat-gateways", "--filter", VF, "Name=state,Values=available,pending") or {}).get("NatGateways", [])
web_ids = {s["SubnetId"] for s in tier["web"]}
check("a NAT Gateway is available and sits in a WEB (public) subnet", bool(nats) and all(n["SubnetId"] in web_ids for n in nats))
check("an internet gateway is attached", len((aws("ec2", "describe-internet-gateways", "--filters", "Name=attachment.vpc-id,Values=" + V) or {}).get("InternetGateways", [])) == 1)

print("== Security groups: each tier trusts only the one in front of it ==")
sgs = {g["GroupName"]: g for g in (aws("ec2", "describe-security-groups", "--filters", VF) or {}).get("SecurityGroups", [])}
def ing(name):
    g = sgs.get(name)
    if not g:
        return None
    return [r for r in (aws("ec2", "describe-security-group-rules", "--filters", "Name=group-id,Values=" + g["GroupId"]) or {}).get("SecurityGroupRules", []) if not r["IsEgress"]]
w, a, d = ing("clippy-web"), ing("clippy-app"), ing("clippy-data")
check("security groups clippy-web, clippy-app and clippy-data exist", None not in (w, a, d))
check("clippy-web: 80 and 443 from anywhere, nothing else", w is not None and sorted(r["FromPort"] for r in w) == [80, 443] and all(r.get("CidrIpv4") == "0.0.0.0/0" for r in w))
check("clippy-app: port 8000 from the clippy-web group only", a is not None and len(a) == 1 and a[0]["FromPort"] == 8000 and a[0].get("ReferencedGroupInfo", {}).get("GroupId") == sgs.get("clippy-web", {}).get("GroupId"))
check("clippy-data: port 5432 from the clippy-app group only", d is not None and len(d) == 1 and d[0]["FromPort"] == 5432 and d[0].get("ReferencedGroupInfo", {}).get("GroupId") == sgs.get("clippy-app", {}).get("GroupId"))

print("== The network ACL on the data subnets (the second lock) ==")
nacls = (aws("ec2", "describe-network-acls", "--filters", VF) or {}).get("NetworkAcls", [])
data_ids = {s["SubnetId"] for s in tier["data"]}
nacl = next((n for n in nacls if not n["IsDefault"] and data_ids and data_ids <= {x["SubnetId"] for x in n["Associations"]}), None)
check("a custom network ACL is associated with BOTH data subnets", nacl is not None)
ent = [e for e in (nacl or {}).get("Entries", []) if e["RuleNumber"] < 32767]
app_cidrs = {s["CidrBlock"] for s in tier["app"]}
inb = {(e.get("CidrBlock"), e.get("PortRange", {}).get("From"), e.get("PortRange", {}).get("To")) for e in ent if not e["Egress"] and e["RuleAction"] == "allow" and e["Protocol"] == "6"}
outb = {(e.get("CidrBlock"), e.get("PortRange", {}).get("From"), e.get("PortRange", {}).get("To")) for e in ent if e["Egress"] and e["RuleAction"] == "allow" and e["Protocol"] == "6"}
check("inbound: TCP 5432 allowed from each app subnet, nothing else allowed", inb == {(c, 5432, 5432) for c in app_cidrs}, "found %s" % sorted(map(str, inb)))
check("outbound: the replies (ephemeral ports 1024-65535) allowed to the app subnets only", outb == {(c, 1024, 65535) for c in app_cidrs}, "found %s" % sorted(map(str, outb)))
check("no rule allows 0.0.0.0/0 on that ACL", not any(e.get("CidrBlock") == "0.0.0.0/0" and e["RuleAction"] == "allow" for e in ent))
print()
print(("ALL CHECKS PASSED (%d/%d)" % (passed, passed)) if failed == 0 else ("%d check(s) failed, %d passed" % (failed, passed)))
sys.exit(1 if failed else 0)
