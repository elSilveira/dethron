"""The Reticulum configuration a node runs on, written where the node lives.

Reticulum reads its configuration from a directory, so a node that carries its own
directory carries its own network with it: two nodes on one machine do not collide, and
moving a node means moving a folder. Nothing here is shared and nothing is discovered —
a node reaches exactly the peers it was told about, which is what makes a claim about
the medium checkable later.
"""

BASE = ('[reticulum]\n share_instance = No\n enable_transport = {transport}\n'
        ' discover_interfaces = No\n[logging]\n loglevel = {loglevel}\n[interfaces]\n')


def config_text(*, port=None, peers=(), serial=None, transport=False, loglevel=3):
    """`port` listens, `peers` are host:port to dial, `serial` is a port that carries no IP.

    A node given a serial link and nothing else has exactly one interface, and it is not
    an IP one. That is not decoration: it is what lets an audit say an object crossed a
    non-IP medium, because the node had no other medium to cross.
    """
    if serial and (port or peers):
        raise ValueError('a serial-only node cannot also listen on or dial an IP address')
    text = BASE.format(transport='Yes' if transport else 'No', loglevel=int(loglevel))
    if port:
        text += (' [[Listener]]\n type = TCPServerInterface\n enabled = Yes\n'
                 f' listen_ip = 0.0.0.0\n listen_port = {int(port)}\n')
    for index, peer in enumerate(peers):
        host, _, remote = str(peer).partition(':')
        if not host or not remote.isdigit():
            raise ValueError(f'a peer is host:port, not {peer!r}')
        text += (f' [[Peer{index}]]\n type = TCPClientInterface\n enabled = Yes\n'
                 f' target_host = {host}\n target_port = {int(remote)}\n')
    if serial:
        text += (' [[Serial]]\n type = SerialInterface\n enabled = Yes\n'
                 f" port = {serial['port']}\n speed = {int(serial.get('speed', 115200))}\n"
                 ' databits = 8\n parity = N\n stopbits = 1\n')
    if not (port or peers or serial):
        raise ValueError('a node with no interface can reach nothing; give a port, a peer or a serial link')
    return text
