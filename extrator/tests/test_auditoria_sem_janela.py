import unittest
from unittest.mock import MagicMock, patch

from extrator.auditoria import get_mac_address


class TestAuditoriaSemJanela(unittest.TestCase):
    def test_consulta_mac_oculta_janela_no_windows(self):
        socket = MagicMock()
        socket.getsockname.return_value = ('192.0.2.1', 1234)
        resultado = MagicMock(stdout='AA-BB-CC-DD-EE-FF')
        with patch('extrator.auditoria.socket.socket', return_value=socket), \
             patch('extrator.auditoria.sys.platform', 'win32'), \
             patch('extrator.auditoria.subprocess.CREATE_NO_WINDOW', 0x08000000, create=True), \
             patch('extrator.auditoria.subprocess.run', return_value=resultado) as executar:
            self.assertEqual(get_mac_address(), 'aa:bb:cc:dd:ee:ff')
        self.assertEqual(executar.call_args.kwargs['creationflags'], 0x08000000)


if __name__ == '__main__':
    unittest.main()
