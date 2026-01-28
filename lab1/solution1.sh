#!/usr/bin/env python3

import subprocess
import time

BRIDGE_NAME = "br0"
BRIDGE_IP = "192.168.100.1/24"
TAP0_NAME = "tap0"
TAP1_NAME = "tap1"
TAP0_IP = "192.168.100.2/24"
TAP1_IP = "192.168.100.3/24"
TAP0_MAC = "00:11:22:33:44:55"
TAP1_MAC = "00:11:22:33:44:66"
VM1_NAME = "vm1"
VM2_NAME = "vm2"
GATEWAY_IP = "192.168.100.1"

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)

def write_file(path, content):
    subprocess.run(f"tee {path}", shell=True, input=content.encode(), stdout=subprocess.DEVNULL)

# Create bridge
run(f"ip link add name {BRIDGE_NAME} type bridge")
run(f"ip addr add {BRIDGE_IP} dev {BRIDGE_NAME}")
run(f"ip link set dev {BRIDGE_NAME} up")

# Create TAP devices with MAC addresses
run(f"ip tuntap add dev {TAP0_NAME} mode tap")
run(f"ip link set dev {TAP0_NAME} address {TAP0_MAC}")
run(f"ip link set dev {TAP0_NAME} up")

run(f"ip tuntap add dev {TAP1_NAME} mode tap")
run(f"ip link set dev {TAP1_NAME} address {TAP1_MAC}")
run(f"ip link set dev {TAP1_NAME} up")

# Add TAPs to bridge
run(f"ip link set dev {TAP0_NAME} master {BRIDGE_NAME}")
run(f"ip link set dev {TAP1_NAME} master {BRIDGE_NAME}")

# Assign IPs to TAP devices
run(f"ip addr add {TAP0_IP} dev {TAP0_NAME}")
run(f"ip addr add {TAP1_IP} dev {TAP1_NAME}")

# Create LXC containers
run(f"lxc-create -n {VM1_NAME} -t ubuntu -- --release focal")
run(f"lxc-create -n {VM2_NAME} -t ubuntu -- --release focal")

# Configure VM1 - use tap0 directly
vm1_config = f"""lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/{VM1_NAME}/rootfs
lxc.uts.name = {VM1_NAME}
lxc.net.0.type = phys
lxc.net.0.link = {TAP0_NAME}
lxc.net.0.flags = up
lxc.net.0.name = eth0
"""
write_file(f"/var/lib/lxc/{VM1_NAME}/config", vm1_config)

# Configure VM2 - use tap1 directly
vm2_config = f"""lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/{VM2_NAME}/rootfs
lxc.uts.name = {VM2_NAME}
lxc.net.0.type = phys
lxc.net.0.link = {TAP1_NAME}
lxc.net.0.flags = up
lxc.net.0.name = eth0
"""
write_file(f"/var/lib/lxc/{VM2_NAME}/config", vm2_config)

# Start containers
run(f"lxc-start -n {VM1_NAME}")
run(f"lxc-start -n {VM2_NAME}")
time.sleep(3)

# Set default route inside VMs
run(f"lxc-attach -n {VM1_NAME} -- ip route add default via {GATEWAY_IP}")
run(f"lxc-attach -n {VM2_NAME} -- ip route add default via {GATEWAY_IP}")
