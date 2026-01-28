#!/bin/bash

BRIDGE_NAME="br0"
BRIDGE_IP="192.168.100.1/24"
TAP0_NAME="tap0"
TAP1_NAME="tap1"
VM1_NAME="vm1"
VM2_NAME="vm2"
VM1_IP="192.168.100.2/24"
VM2_IP="192.168.100.3/24"
GATEWAY_IP="192.168.100.1"

sudo ip link add name $BRIDGE_NAME type bridge
sudo ip addr add $BRIDGE_IP dev $BRIDGE_NAME
sudo ip link set dev $BRIDGE_NAME up

sudo ip tuntap add dev $TAP0_NAME mode tap
sudo ip tuntap add dev $TAP1_NAME mode tap
sudo ip link set dev $TAP0_NAME up
sudo ip link set dev $TAP1_NAME up

sudo ip link set dev $TAP0_NAME master $BRIDGE_NAME
sudo ip link set dev $TAP1_NAME master $BRIDGE_NAME

sudo lxc-create -n $VM1_NAME -t ubuntu -- --release focal
sudo lxc-create -n $VM2_NAME -t ubuntu -- --release focal

cat << EOF | sudo tee /var/lib/lxc/$VM1_NAME/config
lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/$VM1_NAME/rootfs
lxc.uts.name = $VM1_NAME
lxc.net.0.type = veth
lxc.net.0.link = $BRIDGE_NAME
lxc.net.0.flags = up
lxc.net.0.name = eth0
lxc.net.0.hwaddr = 00:16:3e:xx:xx:01
EOF

cat << EOF | sudo tee /var/lib/lxc/$VM2_NAME/config
lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.rootfs.path = dir:/var/lib/lxc/$VM2_NAME/rootfs
lxc.uts.name = $VM2_NAME
lxc.net.0.type = veth
lxc.net.0.link = $BRIDGE_NAME
lxc.net.0.flags = up
lxc.net.0.name = eth0
lxc.net.0.hwaddr = 00:16:3e:xx:xx:02
EOF

sudo lxc-start -n $VM1_NAME
sudo lxc-start -n $VM2_NAME
sleep 3

sudo lxc-attach -n $VM1_NAME -- bash -c "
    ip addr add $VM1_IP dev eth0
    ip link set dev eth0 up
    ip route add default via $GATEWAY_IP
"

sudo lxc-attach -n $VM2_NAME -- bash -c "
    ip addr add $VM2_IP dev eth0
    ip link set dev eth0 up
    ip route add default via $GATEWAY_IP
"
