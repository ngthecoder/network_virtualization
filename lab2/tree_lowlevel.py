#!/usr/bin/python

import sys
from mininet.node import Host, OVSSwitch, Controller
from mininet.link import Link
from mininet.log import setLogLevel
from mininet.util import dumpNodeConnections


def run_experiment(n):
    """Create the tree topology using low-level API and test connectivity."""

    c0 = Controller('c0', inNamespace=False)
    
    core = OVSSwitch('c1', inNamespace=False)

    agg_switches = []
    edge_switches = []
    hosts = []

    for i in range(1, n + 1):
        agg = OVSSwitch('a{}'.format(i), inNamespace=False)
        agg_switches.append(agg)
        Link(agg, core)

        for j in range(1, 3):
            edge_index = 2 * (i - 1) + j

            edge = OVSSwitch('e{}'.format(edge_index), inNamespace=False)
            edge_switches.append(edge)
            Link(edge, agg)

            for k in range(1, 3):
                host_index = 2 * (edge_index - 1) + k

                host = Host('h{}'.format(host_index))
                hosts.append(host)
                Link(host, edge)

                host.setIP('10.0.0.{}/24'.format(host_index))

    c0.start()
    core.start([c0])
    for sw in agg_switches:
        sw.start([c0])
    for sw in edge_switches:
        sw.start([c0])

    print("Dumping host connections")
    dumpNodeConnections(hosts)

    print("Testing network connectivity")
    for i, src in enumerate(hosts):
        for dst in hosts[i + 1:]:
            result = src.cmd('ping -c1 -W1', dst.IP())
            if '1 received' in result:
                print('{} -> {} : OK'.format(src.name, dst.name))
            else:
                print('{} -> {} : FAIL'.format(src.name, dst.name))

    core.stop()
    for sw in agg_switches:
        sw.stop()
    for sw in edge_switches:
        sw.stop()
    c0.stop()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: sudo python tree_lowlevel.py <n>")
        sys.exit(1)

    setLogLevel('info')
    n = int(sys.argv[1])
    run_experiment(n)