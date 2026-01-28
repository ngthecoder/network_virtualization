#!/usr/bin/env python3

import subprocess
import time

BRIDGE_NAME = "br0"
BRIDGE_IP = "192.168.100.1/24"
VM1_NAME = "vm1"
VM2_NAME = "vm2"
VM1_IP = "192.168.100.2/24"
VM2_IP = "192.168.100.3/24"
VM1_MAC = "00:11:22:33:44:55"
VM2_MAC = "00:11:22:33:44:66"
GATEWAY_IP = "192.168.100.1"

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)

def run_ignore(cmd):
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

def write_file(path, content):
    subprocess.run(f"tee {path}", shell=True, input=content.encode(), stdout=subprocess.DEVNULL)

# Create bridge
run(f"ip link add name {BRIDGE_NAME} type bridge")
run(f"ip addr add {BRIDGE_IP} dev {BRIDGE_NAME}")
run(f"ip link set dev {BRIDGE_NAME} up")

# Create LXC containers
run_ignore(f"lxc-create -n {VM1_NAME} -t ubuntu -- --release focal")
run_ignore(f"lxc-create -n {VM2_NAME} -t ubuntu -- --release focal")

# Configure VM1
vm1_config = f"""lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/{VM1_NAME}/rootfs
lxc.uts.name = {VM1_NAME}
lxc.net.0.type = veth
lxc.net.0.link = {BRIDGE_NAME}
lxc.net.0.flags = up
lxc.net.0.name = eth0
lxc.net.0.veth.pair = tap0
lxc.net.0.hwaddr = {VM1_MAC}
"""
write_file(f"/var/lib/lxc/{VM1_NAME}/config", vm1_config)

# Configure VM2
vm2_config = f"""lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/{VM2_NAME}/rootfs
lxc.uts.name = {VM2_NAME}
lxc.net.0.type = veth
lxc.net.0.link = {BRIDGE_NAME}
lxc.net.0.flags = up
lxc.net.0.name = eth0
lxc.net.0.veth.pair = tap1
lxc.net.0.hwaddr = {VM2_MAC}
"""
write_file(f"/var/lib/lxc/{VM2_NAME}/config", vm2_config)

# Start containers
run(f"lxc-start -n {VM1_NAME}")
run(f"lxc-start -n {VM2_NAME}")
time.sleep(3)

# Configure IPs inside containers
run(f"lxc-attach -n {VM1_NAME} -- ip addr add {VM1_IP} dev eth0")
run(f"lxc-attach -n {VM1_NAME} -- ip link set eth0 up")
run(f"lxc-attach -n {VM1_NAME} -- ip route add default via {GATEWAY_IP}")

run(f"lxc-attach -n {VM2_NAME} -- ip addr add {VM2_IP} dev eth0")
run(f"lxc-attach -n {VM2_NAME} -- ip link set eth0 up")
run(f"lxc-attach -n {VM2_NAME} -- ip route add default via {GATEWAY_IP}")
