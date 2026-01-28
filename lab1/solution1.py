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

# Create TAP devices with IPs and MACs
run(f"ip tuntap add dev {TAP0_NAME} mode tap")
run(f"ip link set dev {TAP0_NAME} address {TAP0_MAC}")
run(f"ip link set dev {TAP0_NAME} master {BRIDGE_NAME}")
run(f"ip link set dev {TAP0_NAME} up")

run(f"ip tuntap add dev {TAP1_NAME} mode tap")
run(f"ip link set dev {TAP1_NAME} address {TAP1_MAC}")
run(f"ip link set dev {TAP1_NAME} master {BRIDGE_NAME}")
run(f"ip link set dev {TAP1_NAME} up")

# Create LXC containers
run(f"lxc-create -n {VM1_NAME} -t ubuntu -- --release focal")
run(f"lxc-create -n {VM2_NAME} -t ubuntu -- --release focal")

# Configure VM1 - use veth connected to bridge
vm1_config = f"""lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/{VM1_NAME}/rootfs
lxc.uts.name = {VM1_NAME}
lxc.net.0.type = veth
lxc.net.0.link = {BRIDGE_NAME}
lxc.net.0.flags = up
lxc.net.0.name = eth0
lxc.net.0.hwaddr = {TAP0_MAC}
lxc.net.0.ipv4.address = {TAP0_IP}
lxc.net.0.ipv4.gateway = {GATEWAY_IP}
"""
write_file(f"/var/lib/lxc/{VM1_NAME}/config", vm1_config)

# Configure VM2 - use veth connected to bridge
vm2_config = f"""lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/{VM2_NAME}/rootfs
lxc.uts.name = {VM2_NAME}
lxc.net.0.type = veth
lxc.net.0.link = {BRIDGE_NAME}
lxc.net.0.flags = up
lxc.net.0.name = eth0
lxc.net.0.hwaddr = {TAP1_MAC}
lxc.net.0.ipv4.address = {TAP1_IP}
lxc.net.0.ipv4.gateway = {GATEWAY_IP}
"""
write_file(f"/var/lib/lxc/{VM2_NAME}/config", vm2_config)

# Start containers
run(f"lxc-start -n {VM1_NAME}")
run(f"lxc-start -n {VM2_NAME}")
time.sleep(3)
