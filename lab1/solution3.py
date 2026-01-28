#!/usr/bin/env python3

import subprocess
import time

BRIDGE_NAME = "br0"
VM1_NAME = "vm1"
VM2_NAME = "vm2"
VM1_MAC = "00:11:22:33:44:55"
VM2_MAC = "00:11:22:33:44:66"

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)

def run_ignore(cmd):
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

def get_output(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip().split('\n')[0].strip()

def write_file(path, content):
    subprocess.run(f"tee {path}", shell=True, input=content.encode(), stdout=subprocess.DEVNULL)

# Detect external interface and current config
EXTERNAL_IF = get_output("ip route | grep default | awk '{print $5}' | head -1")
CURRENT_IP = get_output(f"ip addr show {EXTERNAL_IF} | grep 'inet ' | head -1 | awk '{{print $2}}'")
CURRENT_GW = get_output("ip route | grep default | head -1 | awk '{print $3}'")

print(f"External IF: {EXTERNAL_IF}")
print(f"Current IP: {CURRENT_IP}")
print(f"Current GW: {CURRENT_GW}")

# Create bridge
run(f"ip link add name {BRIDGE_NAME} type bridge")
run(f"ip link set dev {BRIDGE_NAME} up")

# Add physical interface to bridge
run(f"ip link set dev {EXTERNAL_IF} master {BRIDGE_NAME}")

# Move IP from physical interface to bridge
run_ignore(f"ip addr del {CURRENT_IP} dev {EXTERNAL_IF}")
run(f"ip addr add {CURRENT_IP} dev {BRIDGE_NAME}")
run_ignore("ip route del default")
run(f"ip route add default via {CURRENT_GW}")

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

# Request DHCP inside containers
run_ignore(f"lxc-attach -n {VM1_NAME} -- ip link set eth0 up")
run_ignore(f"lxc-attach -n {VM1_NAME} -- dhclient eth0")

run_ignore(f"lxc-attach -n {VM2_NAME} -- ip link set eth0 up")
run_ignore(f"lxc-attach -n {VM2_NAME} -- dhclient eth0")
