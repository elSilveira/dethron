"""Unit boundary test; this fake router is never used by the real experiment."""
import unittest
from unittest.mock import Mock, patch

try:
    import RNS
except ImportError as exc:
    raise unittest.SkipTest("requires .venv-gateway") from exc

from dethron.adapter import Adapter


class AdapterTests(unittest.TestCase):
    def test_known_identity_without_cached_path_delegates_to_native_router(self):
        identity = RNS.Identity()
        source = RNS.Destination(RNS.Identity(), RNS.Destination.OUT,
                                 RNS.Destination.SINGLE, "lxmf", "delivery")
        router = Mock()
        adapter = Adapter(router, source, Mock(), Mock())
        with patch.object(RNS.Identity, "recall", return_value=identity), \
             patch.object(RNS.Transport, "has_path", return_value=False), \
             patch.object(RNS.Transport, "request_path"):
            accepted = adapter.transmit(RNS.Destination.hash(identity, "lxmf", "delivery").hex(), b"test")
        self.assertTrue(accepted, "native router can use backchannel or discover a path")
        router.handle_outbound.assert_called_once()


if __name__ == "__main__":
    unittest.main()
