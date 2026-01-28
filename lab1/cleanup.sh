#!/usr/bin/env python3

import subprocess

BRIDGE_NAME = "br0"
TAP0_NAME = "tap0"
TAP1_NAME = "tap1"
VM1_NAME = "vm1"
VM2_NAME = "vm2"
BRIDGE_NET = "192.168.100.0/24"

def run(cmd):
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL)

run(f"lxc-stop -n {VM1_NAME}")
run(f"lxc-stop -n {VM2_NAME}")

run(f"lxc-destroy -n {VM1_NAME}")
run(f"lxc-destroy -n {VM2_NAME}")

run(f"ip link delete {TAP0_NAME}")
run(f"ip link delete {TAP1_NAME}")
run(f"ip link delete {BRIDGE_NAME}")

run(f"iptables -t nat -D POSTROUTING -s {BRIDGE_NET} -j MASQUERADE")
run(f"iptables -D FORWARD -i {BRIDGE_NAME} -j ACCEPT")
run(f"iptables -D FORWARD -o {BRIDGE_NAME} -j ACCEPT")

run("sysctl -w net.ipv4.ip_forward=0")
