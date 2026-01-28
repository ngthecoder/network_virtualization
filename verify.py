#!/usr/bin/env python3

import subprocess

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr

print("=" * 50)
print("Solution 3 Verification")
print("=" * 50)

print("\n[1] Bridge members:")
print(run("bridge link show"))

print("\n[2] Bridge IP:")
print(run("ip addr show br0 | grep inet"))

print("\n[3] Container status:")
print(run("lxc-ls -f"))

print("\n[4] VM1 eth0:")
print(run("lxc-attach -n vm1 -- ip addr show eth0"))

print("\n[5] VM2 eth0:")
print(run("lxc-attach -n vm2 -- ip addr show eth0"))

print("\n[6] VM1 -> Internet (8.8.8.8):")
print(run("lxc-attach -n vm1 -- ping -c 2 8.8.8.8"))

print("\n[7] VM1 -> VM2:")
vm2_ip = run("lxc-attach -n vm2 -- ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1").strip()
if vm2_ip:
    print(f"VM2 IP: {vm2_ip}")
    print(run(f"lxc-attach -n vm1 -- ping -c 2 {vm2_ip}"))
else:
    print("Could not get VM2 IP")

print("=" * 50)
print("Verification complete")
print("=" * 50)
