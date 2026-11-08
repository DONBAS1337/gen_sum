import io
import os
import sys
import unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'don_gen'))
import dg_backend as backend


class TransportFallback(unittest.TestCase):
    def test_local_schannel_failure_uses_verified_python_tls(self):
        response = io.BytesIO(b'data: done')
        opener = mock.Mock()
        opener.open.return_value = response
        tls = object()
        with mock.patch.object(backend.os, 'name', 'nt'), \
                mock.patch.object(backend, '_curl_response_open', side_effect=backend._CurlTLSUnavailable('local')), \
                mock.patch.object(backend, '_ssl_context', return_value=tls), \
                mock.patch.object(backend, 'HTTPSHandler') as handler, \
                mock.patch.object(backend, 'build_opener', return_value=opener):
            result = backend._http_open(backend.BACKEND + '/responses', b'{}')
        self.assertIs(result, response)
        handler.assert_called_once_with(context=tls)
        self.assertEqual(opener.open.call_count, 1)

    def test_partial_generation_or_timeout_is_never_replayed(self):
        for code, status, payload, error in (
                (28, 200, b'data: partial', b'timeout'),
                (35, 200, b'data: partial', b'SEC_E_NO_CREDENTIALS'),
                (35, 0, b'', b'certificate invalid')):
            process = mock.Mock(returncode=code)
            process.communicate.return_value = (payload + b'\n__DG_HTTP_CODE__:' + str(status).encode('ascii'), error)
            with mock.patch.object(backend.os, 'name', 'nt'), \
                    mock.patch.object(backend.subprocess, 'Popen', return_value=process), \
                    mock.patch.object(backend, 'build_opener') as opener:
                with self.assertRaises(backend.ClientError):
                    backend._http_open(backend.BACKEND + '/responses', b'{}')
                opener.assert_not_called()

    def test_exact_local_error_is_identified_before_fallback(self):
        process = mock.Mock(returncode=35)
        process.communicate.return_value = (b'\n__DG_HTTP_CODE__:000', b'SEC_E_NO_CREDENTIALS')
        with mock.patch.object(backend.os, 'name', 'nt'), \
                mock.patch.object(backend.subprocess, 'Popen', return_value=process):
            with self.assertRaises(backend._CurlTLSUnavailable):
                backend._curl_response_open(backend.BACKEND + '/responses', b'{}', {})
