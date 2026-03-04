#!/usr/bin/env python3
"""
Virtual Network Function: Firewall using Open vSwitch

Implements a multi-table OpenFlow pipeline on an OVS bridge (br0):
    Table 0: VLAN Tagging      - Tag internal (VLAN 10) and external (VLAN 20) traffic
    Table 1: MAC Learning       - Dynamically learn source MAC-to-port mappings
    Table 2: IP Routing         - Forward packets based on destination IP address
    Table 3: Firewall Rules     - Stateless firewall (allow internal->external, block reverse)
    Table 4: QoS                - Prioritize port 1 (internal) over port 2 (external)
    Table 5: NAT                - Translate internal IP (10.0.0.1) to public IP (10.0.0.100)
    Table 6: Final Output       - Strip VLAN tags and forward to destination port

Network topology:
    [ns-internal]              [br0]                [ns-external]
     10.0.0.1  <--veth pair--> port 1  port 2 <--veth pair-->  10.0.0.2
     VLAN 10                                                    VLAN 20
                           NAT public IP: 10.0.0.100
"""

import subprocess
import sys
import time

# ─── Configuration ──────────────────────────────────────────────────────────

BRIDGE      = "br0"
INT_NS      = "ns-internal"       # Internal host namespace
EXT_NS      = "ns-external"       # External host namespace
INT_VETH    = "veth-int"          # veth endpoint inside internal namespace
INT_VETH_BR = "veth-int-br"       # veth endpoint on bridge (port 1)
EXT_VETH    = "veth-ext"          # veth endpoint inside external namespace
EXT_VETH_BR = "veth-ext-br"       # veth endpoint on bridge (port 2)
INT_IP      = "10.0.0.1"          # Internal host IP (private)
EXT_IP      = "10.0.0.2"          # External host IP
NAT_IP      = "10.0.0.100"        # NAT public IP (what external hosts see)
SUBNET      = "24"


def run(cmd, check=True, capture=False):
    """Execute a shell command and optionally capture output."""
    result = subprocess.run(
        cmd, shell=True, check=check,
        capture_output=True, text=True
    )
    if capture and result.stdout.strip():
        print(result.stdout.strip())
    if capture and result.stderr.strip() and result.returncode != 0:
        print(result.stderr.strip())
    return result


def cleanup():
    """Remove all OVS bridges, namespaces, and veth pairs."""
    print("Cleaning up previous configuration...")
    run(f"ip netns exec {INT_NS} pkill -f 'nc ' 2>/dev/null", check=False)
    run(f"ip netns exec {INT_NS} pkill -f 'nc -l' 2>/dev/null", check=False)
    run(f"ovs-vsctl --if-exists del-br {BRIDGE}", check=False)
    run(f"ip netns del {INT_NS} 2>/dev/null", check=False)
    run(f"ip netns del {EXT_NS} 2>/dev/null", check=False)
    run(f"ip link del {INT_VETH_BR} 2>/dev/null", check=False)
    run(f"ip link del {EXT_VETH_BR} 2>/dev/null", check=False)
    print("Cleanup complete.\n")


def setup_namespaces():
    """Create network namespaces and veth pairs to simulate internal/external hosts."""
    print("Setting up network namespaces and veth pairs...")

    # Create namespaces (isolated network environments)
    run(f"ip netns add {INT_NS}")
    run(f"ip netns add {EXT_NS}")

    # Create veth pairs (virtual ethernet cables)
    # Each pair has two ends: one goes in the namespace, one stays on the bridge
    run(f"ip link add {INT_VETH_BR} type veth peer name {INT_VETH}")
    run(f"ip link add {EXT_VETH_BR} type veth peer name {EXT_VETH}")

    # Move one end of each veth pair into the corresponding namespace
    run(f"ip link set {INT_VETH} netns {INT_NS}")
    run(f"ip link set {EXT_VETH} netns {EXT_NS}")

    # Configure internal host (10.0.0.1)
    run(f"ip netns exec {INT_NS} ip addr add {INT_IP}/{SUBNET} dev {INT_VETH}")
    run(f"ip netns exec {INT_NS} ip link set {INT_VETH} up")
    run(f"ip netns exec {INT_NS} ip link set lo up")

    # Configure external host (10.0.0.2)
    run(f"ip netns exec {EXT_NS} ip addr add {EXT_IP}/{SUBNET} dev {EXT_VETH}")
    run(f"ip netns exec {EXT_NS} ip link set {EXT_VETH} up")
    run(f"ip netns exec {EXT_NS} ip link set lo up")

    # Bring up bridge-side veth endpoints
    run(f"ip link set {INT_VETH_BR} up")
    run(f"ip link set {EXT_VETH_BR} up")
    print("Namespaces and veth pairs configured.\n")


def setup_bridge():
    """Create OVS bridge and add ports."""
    print("Setting up OVS bridge...")

    # Create the bridge
    run(f"ovs-vsctl add-br {BRIDGE}")

    # Add veth bridge-side endpoints as ports
    # Port 1 = internal, Port 2 = external
    run(f"ovs-vsctl add-port {BRIDGE} {INT_VETH_BR}")
    run(f"ovs-vsctl add-port {BRIDGE} {EXT_VETH_BR}")
    run(f"ip link set {BRIDGE} up")

    # Clear any default flows so we start with a clean pipeline
    run(f"ovs-ofctl del-flows {BRIDGE}")
    print("OVS bridge configured.\n")


def setup_qos():
    """Configure QoS queues for traffic prioritization.

    Queue 0 (high priority): 8-10 Mbps — for internal (port 1) traffic
    Queue 1 (low priority):  1-5  Mbps — for external (port 2) traffic
    """
    print("Setting up QoS queues...")

    # Apply QoS policy to internal-facing port
    run(f"ovs-vsctl set port {INT_VETH_BR} qos=@newqos -- "
        f"--id=@newqos create qos type=linux-htb "
        f"other-config:max-rate=10000000 "
        f"queues:0=@q0 queues:1=@q1 -- "
        f"--id=@q0 create queue other-config:min-rate=8000000 "
        f"other-config:max-rate=10000000 -- "
        f"--id=@q1 create queue other-config:min-rate=1000000 "
        f"other-config:max-rate=5000000")

    # Apply QoS policy to external-facing port
    run(f"ovs-vsctl set port {EXT_VETH_BR} qos=@newqos -- "
        f"--id=@newqos create qos type=linux-htb "
        f"other-config:max-rate=10000000 "
        f"queues:0=@q0 queues:1=@q1 -- "
        f"--id=@q0 create queue other-config:min-rate=8000000 "
        f"other-config:max-rate=10000000 -- "
        f"--id=@q1 create queue other-config:min-rate=1000000 "
        f"other-config:max-rate=5000000")
    print("QoS queues configured.\n")


def add_flow(flow):
    """Add a single OpenFlow rule to the bridge."""
    run(f"ovs-ofctl add-flow {BRIDGE} \"{flow}\"")


def setup_flows():
    """Configure the complete multi-table OpenFlow pipeline."""

    # ── Table 0: VLAN Tagging ───────────────────────────────────────────────
    #
    # Purpose: Classify traffic by origin. Packets from port 1 (internal)
    # get tagged with VLAN 10, packets from port 2 (external) get VLAN 20.
    # This tag follows the packet through the entire pipeline so later
    # tables can make decisions based on traffic direction.

    print("Configuring Table 0: VLAN Tagging...")
    add_flow("table=0,priority=100,in_port=1,"
             "actions=mod_vlan_vid:10,resubmit(,1)")
    add_flow("table=0,priority=100,in_port=2,"
             "actions=mod_vlan_vid:20,resubmit(,1)")
    add_flow("table=0,priority=0,actions=drop")

    # ── Table 1: MAC Learning ───────────────────────────────────────────────
    #
    # Purpose: Dynamically learn which MAC address is behind which port.
    # The 'learn' action creates entries in table 10: when a packet arrives
    # with src MAC X on port Y, it records "if dst MAC = X, output port = Y".
    # This mimics how real switches build their forwarding tables.

    print("Configuring Table 1: MAC Learning...")
    add_flow("table=1,priority=100,"
             "actions=learn(table=10,hard_timeout=300,priority=100,"
             "NXM_OF_ETH_DST[]=NXM_OF_ETH_SRC[],"
             "load:NXM_OF_IN_PORT[]->NXM_NX_REG0[0..15]),"
             "resubmit(,2)")
    add_flow("table=1,priority=0,actions=drop")

    # ── Table 2: IP Routing ─────────────────────────────────────────────────
    #
    # Purpose: Determine output port based on destination IP address.
    # The output port number is stored in register 0 (reg0) so that
    # table 6 knows where to send the packet after all processing.
    # ARP packets are flooded to both ports (they bypass tables 3-6
    # since ARP doesn't need firewall/QoS/NAT processing).

    print("Configuring Table 2: IP Routing...")
    add_flow("table=2,priority=200,arp,"
             "actions=strip_vlan,output:1,output:2")
    add_flow(f"table=2,priority=100,ip,nw_dst={INT_IP},"
             f"actions=load:1->NXM_NX_REG0[0..15],resubmit(,3)")
    add_flow(f"table=2,priority=100,ip,nw_dst={EXT_IP},"
             f"actions=load:2->NXM_NX_REG0[0..15],resubmit(,3)")
    add_flow(f"table=2,priority=100,ip,nw_dst={NAT_IP},"
             f"actions=load:1->NXM_NX_REG0[0..15],resubmit(,3)")
    add_flow("table=2,priority=0,actions=drop")

    # ── Table 3: Firewall Rules ─────────────────────────────────────────────
    #
    # Purpose: Stateless packet filter.
    #   - Internal (VLAN 10) → External: ALLOW all traffic
    #   - External (VLAN 20) → Internal: BLOCK by default, with exceptions:
    #       * ICMP echo-reply (type 0): allowed so internal pings get responses
    #       * TCP port 80 (HTTP): allowed
    #       * TCP port 22 (SSH): explicitly blocked
    #
    # Note: This is a stateless firewall — it cannot track connections.
    # Reply traffic from external must be explicitly permitted.

    print("Configuring Table 3: Firewall Rules...")
    # Allow all internal-originated traffic
    add_flow("table=3,priority=100,dl_vlan=10,"
             "actions=resubmit(,4)")
    # Allow ICMP echo-reply from external (for ping responses)
    add_flow("table=3,priority=200,dl_vlan=20,icmp,icmp_type=0,"
             "actions=resubmit(,4)")
    # Allow HTTP from external (TCP destination port 80)
    add_flow("table=3,priority=200,dl_vlan=20,tcp,tp_dst=80,"
             "actions=resubmit(,4)")
    # Block SSH from external (TCP destination port 22)
    add_flow("table=3,priority=200,dl_vlan=20,tcp,tp_dst=22,"
             "actions=drop")
    # Block all other external-originated traffic
    add_flow("table=3,priority=50,dl_vlan=20,"
             "actions=drop")
    # Default: drop unmatched packets
    add_flow("table=3,priority=0,actions=drop")

    # ── Table 4: Quality of Service ─────────────────────────────────────────
    #
    # Purpose: Assign packets to QoS queues for bandwidth management.
    # Internal traffic (port 1) → queue 0 (high priority, 8-10 Mbps)
    # External traffic (port 2) → queue 1 (low priority, 1-5 Mbps)

    print("Configuring Table 4: QoS...")
    add_flow("table=4,priority=100,in_port=1,"
             "actions=set_queue:0,resubmit(,5)")
    add_flow("table=4,priority=100,in_port=2,"
             "actions=set_queue:1,resubmit(,5)")
    add_flow("table=4,priority=0,actions=resubmit(,5)")

    # ── Table 5: NAT (Network Address Translation) ──────────────────────────
    #
    # Purpose: Translate private IPs to public IPs for outbound traffic.
    #   Outbound (from internal, VLAN 10):
    #       Source IP 10.0.0.1 → 10.0.0.100 (public NAT IP)
    #   Inbound (destined to NAT IP):
    #       Destination IP 10.0.0.100 → 10.0.0.1 (real internal IP)
    #
    # This is how home routers work: internal devices share one public IP.

    print("Configuring Table 5: NAT...")
    add_flow(f"table=5,priority=100,ip,dl_vlan=10,"
             f"actions=mod_nw_src:{NAT_IP},resubmit(,6)")
    add_flow(f"table=5,priority=100,ip,nw_dst={NAT_IP},"
             f"actions=mod_nw_dst:{INT_IP},resubmit(,6)")
    add_flow("table=5,priority=0,actions=resubmit(,6)")

    # ── Table 6: Final Output Processing ────────────────────────────────────
    #
    # Purpose: Strip the VLAN tag (it was only needed for internal pipeline
    # decisions) and send the packet out the port stored in reg0.

    print("Configuring Table 6: Final Output...")
    add_flow("table=6,priority=100,reg0=1,"
             "actions=strip_vlan,output:1")
    add_flow("table=6,priority=100,reg0=2,"
             "actions=strip_vlan,output:2")
    add_flow("table=6,priority=0,actions=drop")

    print("All flow tables configured.\n")


def setup_static_arp():
    """Set static ARP entries so hosts can resolve each other's MACs.

    Without these, ARP requests for the NAT IP (10.0.0.100) would go
    unanswered since no interface actually has that IP configured.
    """
    print("Setting up static ARP entries...")

    int_mac = run(
        f"ip netns exec {INT_NS} cat /sys/class/net/{INT_VETH}/address",
        capture=False
    ).stdout.strip()
    ext_mac = run(
        f"ip netns exec {EXT_NS} cat /sys/class/net/{EXT_VETH}/address",
        capture=False
    ).stdout.strip()

    # Internal needs to know external's MAC
    run(f"ip netns exec {INT_NS} arp -s {EXT_IP} {ext_mac}")
    # External needs to know internal's MAC (for direct access)
    run(f"ip netns exec {EXT_NS} arp -s {INT_IP} {int_mac}")
    # External needs to know NAT IP's MAC (same as internal's MAC)
    run(f"ip netns exec {EXT_NS} arp -s {NAT_IP} {int_mac}")

    print(f"  Internal MAC: {int_mac}")
    print(f"  External MAC: {ext_mac}")
    print("Static ARP entries configured.\n")


def verify():
    """Display bridge configuration, port mapping, and all flow rules."""
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    print("\n--- OVS Bridge Configuration ---")
    run(f"ovs-vsctl show", capture=True)

    print("\n--- OpenFlow Port Mapping ---")
    run(f"ovs-ofctl dump-ports-desc {BRIDGE}", capture=True)

    print("\n--- All Flow Rules ---")
    run(f"ovs-ofctl dump-flows {BRIDGE}", capture=True)

    print("\n--- QoS Configuration ---")
    run(f"ovs-vsctl list qos", capture=True)

    print("\n--- Queue Configuration ---")
    run(f"ovs-vsctl list queue", capture=True)


def test():
    """Run connectivity and firewall tests to validate the pipeline."""
    print("\n" + "=" * 60)
    print("TESTING")
    print("=" * 60)

    # ── Test 1: Ping internal → external (should SUCCEED) ──────────────────
    print("\n--- Test 1: Ping internal -> external (expect SUCCESS) ---")
    print("  Internal (10.0.0.1) pings External (10.0.0.2)")
    print("  Path: Table 0(VLAN 10) -> 1(learn) -> 2(route to port 2) -> "
          "3(VLAN 10 allowed) -> 4(queue 0) -> 5(NAT src->10.0.0.100) -> "
          "6(output port 2)")
    run(f"ip netns exec {INT_NS} ping -c 3 {EXT_IP}", capture=True, check=False)

    # ── Test 2: Ping external → internal (should be BLOCKED) ───────────────
    print("\n--- Test 2: Ping external -> NAT IP (expect BLOCKED) ---")
    print("  External (10.0.0.2) pings NAT IP (10.0.0.100)")
    print("  Path: Table 0(VLAN 20) -> 1(learn) -> 2(route to port 1) -> "
          "3(VLAN 20, ICMP type 8 = echo-request, BLOCKED)")
    run(f"ip netns exec {EXT_NS} ping -c 3 -W 2 {NAT_IP}",
        capture=True, check=False)

    # ── Test 3: HTTP external → internal (should SUCCEED) ──────────────────
    print("\n--- Test 3: HTTP external -> internal port 80 (expect SUCCESS) ---")
    print("  Starting nc listener on internal host (port 80)...")
    run(f"ip netns exec {INT_NS} timeout 5 nc -l -p 80 &>/dev/null &",
        check=False)
    time.sleep(1)

    print("  External connects to NAT IP on port 80 via nc")
    print("  Path: Table 0(VLAN 20) -> 1 -> 2(route to port 1) -> "
          "3(VLAN 20, TCP dst 80 ALLOWED) -> 4(queue 1) -> "
          "5(NAT dst->10.0.0.1) -> 6(output port 1)")
    result = run(
        f"timeout 5 ip netns exec {EXT_NS} bash -c 'echo test | nc -w 2 {NAT_IP} 80'",
        capture=True, check=False
    )
    if result.returncode == 0:
        print("  HTTP (port 80) connection SUCCEEDED (expected)")
    else:
        print("  HTTP (port 80) connection FAILED (unexpected)")

    run(f"ip netns exec {INT_NS} pkill -f 'nc -l' 2>/dev/null", check=False)

    # ── Test 4: SSH external → internal (should be BLOCKED) ────────────────
    print("\n--- Test 4: SSH external -> internal port 22 (expect BLOCKED) ---")
    print("  Starting nc listener on internal host (port 22)...")
    run(f"ip netns exec {INT_NS} timeout 5 nc -l -p 22 &>/dev/null &",
        check=False)
    time.sleep(0.5)

    print("  External attempts TCP connection to NAT IP on port 22")
    print("  Path: Table 0(VLAN 20) -> 1 -> 2(route to port 1) -> "
          "3(VLAN 20, TCP dst 22 DROPPED)")
    result = run(
        f"timeout 5 ip netns exec {EXT_NS} bash -c 'echo test | nc -w 2 {NAT_IP} 22'",
        capture=True, check=False
    )
    if result.returncode != 0:
        print("  SSH connection BLOCKED (expected)")
    else:
        print("  SSH connection succeeded (unexpected!)")

    run(f"ip netns exec {INT_NS} pkill -f 'nc -l' 2>/dev/null", check=False)

    # ── Dump learned MAC entries and flow statistics ───────────────────────
    print("\n--- Learned MAC Entries (Table 10) ---")
    run(f"ovs-ofctl dump-flows {BRIDGE} table=10", capture=True)

    print("\n--- Flow Statistics (packet/byte counts) ---")
    run(f"ovs-ofctl dump-flows {BRIDGE}", capture=True)

    print("\n--- Port Statistics ---")
    run(f"ovs-ofctl dump-ports {BRIDGE}", capture=True)


def main():
    """Main entry point: setup, verify, and test the firewall pipeline."""
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        cleanup()
        sys.exit(0)

    print("=" * 60)
    print("OVS Virtual Network Function: Firewall")
    print("=" * 60 + "\n")

    cleanup()
    setup_namespaces()
    setup_bridge()
    setup_qos()
    setup_flows()
    setup_static_arp()
    verify()
    test()

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Run 'sudo python3 firewall.py cleanup' to remove all configuration.")


if __name__ == "__main__":
    main()