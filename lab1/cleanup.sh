#!/bin/bash

BRIDGE_NAME="br0"
TAP0_NAME="tap0"
TAP1_NAME="tap1"
VM1_NAME="vm1"
VM2_NAME="vm2"
BRIDGE_NET="192.168.100.0/24"

sudo lxc-stop -n $VM1_NAME 2>/dev/null || true
sudo lxc-stop -n $VM2_NAME 2>/dev/null || true

sudo lxc-destroy -n $VM1_NAME 2>/dev/null || true
sudo lxc-destroy -n $VM2_NAME 2>/dev/null || true

sudo ip link delete $TAP0_NAME 2>/dev/null || true
sudo ip link delete $TAP1_NAME 2>/dev/null || true
sudo ip link delete $BRIDGE_NAME 2>/dev/null || true

sudo iptables -t nat -D POSTROUTING -s $BRIDGE_NET -j MASQUERADE 2>/dev/null || true
sudo iptables -D FORWARD -i $BRIDGE_NAME -j ACCEPT 2>/dev/null || true
sudo iptables -D FORWARD -o $BRIDGE_NAME -j ACCEPT 2>/dev/null || true

sudo sysctl -w net.ipv4.ip_forward=0 2>/dev/null || true
