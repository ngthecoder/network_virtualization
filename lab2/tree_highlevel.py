#!/usr/bin/python

import sys
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.util import dumpNodeConnections


class TreeTopo(Topo):
    def build(self, n=2):
        core = self.addSwitch('c1')
        
        for i in range(1, n + 1):
            agg = self.addSwitch('a{}'.format(i))
            self.addLink(agg, core)
            
            for j in range(1, 3):
                edge_index = 2 * (i - 1) + j
                edge = self.addSwitch('e{}'.format(edge_index))
                self.addLink(edge, agg)

                for k in range(1, 3):
                    host_index = 2 * (edge_index - 1) + k
                    host = self.addHost('h{}'.format(host_index))
                    self.addLink(host, edge)


def run_experiment(n):
    """Create the tree topology, start the network, and open the CLI."""
    topo = TreeTopo(n=n)
    net = Mininet(topo=topo)
    net.start()

    print("Dumping host connections")
    dumpNodeConnections(net.hosts)

    print("Testing network connectivity")
    net.pingAll()

    CLI(net)
    net.stop()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: sudo python tree_highlevel.py <n>")
        sys.exit(1)

    setLogLevel('info')
    n = int(sys.argv[1])
    run_experiment(n)