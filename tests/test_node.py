"""What a node refuses before it ever reaches the network.

A contact that is not a contact, a relay that is not a relay, and a node with nothing to
talk over are all mistakes worth catching at the call, not after a timeout blaming the far
end.
"""
import unittest

from dethron.config import config_text
from dethron.node import parse_contact, parse_relay

CONTACT = '0'*32+'.'+'a'*128
RELAY = '127.0.0.1:45810/'+'b'*32


class ContactTests(unittest.TestCase):
    def test_a_well_formed_contact_splits_into_address_and_key(self):
        self.assertEqual(parse_contact(CONTACT), ('0'*32, 'a'*128))
        self.assertEqual(parse_contact('  '+CONTACT+'\n'), ('0'*32, 'a'*128))

    def test_an_address_without_a_key_is_refused(self):
        """An address alone names a destination nobody can verify answers at."""
        with self.assertRaises(ValueError):
            parse_contact('0'*32)

    def test_wrong_lengths_and_non_hex_are_refused(self):
        for bad in ('0'*31+'.'+'a'*128, '0'*32+'.'+'a'*127, 'z'*32+'.'+'a'*128, '', '.'):
            with self.subTest(contact=bad[:20]), self.assertRaises(ValueError):
                parse_contact(bad)


class RelayTests(unittest.TestCase):
    def test_a_relay_is_an_endpoint_and_a_propagation_address(self):
        self.assertEqual(parse_relay(RELAY), ('127.0.0.1:45810', 'b'*32))

    def test_an_endpoint_without_a_propagation_address_is_refused(self):
        for bad in ('127.0.0.1:45810', '127.0.0.1:45810/', 'no-port/'+'b'*32, ''):
            with self.subTest(relay=bad), self.assertRaises(ValueError):
                parse_relay(bad)


class ConfigTests(unittest.TestCase):
    def test_a_listener_and_peers_become_interfaces(self):
        text = config_text(port=45810, peers=['10.0.0.2:45810'])
        self.assertIn('listen_port = 45810', text)
        self.assertIn('target_host = 10.0.0.2', text)
        self.assertIn('enable_transport = No', text)

    def test_a_node_with_no_interface_is_refused(self):
        """It would start cleanly and reach nothing, which is worse than failing."""
        with self.assertRaises(ValueError) as caught:
            config_text()
        self.assertIn('can reach nothing', str(caught.exception))

    def test_a_malformed_peer_is_refused(self):
        for bad in ('10.0.0.2', '10.0.0.2:', ':45810', '10.0.0.2:port'):
            with self.subTest(peer=bad), self.assertRaises(ValueError):
                config_text(peers=[bad])

    def test_a_serial_link_is_the_only_interface_it_gets(self):
        """An interface it never uses is still a path it had, so IP and serial cannot mix."""
        text = config_text(serial={'port': 'COM3'})
        self.assertIn('type = SerialInterface', text)
        self.assertNotIn('TCP', text)
        with self.assertRaises(ValueError):
            config_text(port=45810, serial={'port': 'COM3'})


if __name__ == '__main__':
    unittest.main()
