import os
import unittest
from unittest import mock


class TestParseBool(unittest.TestCase):
    def test_true_values(self):
        from config.settings import _parse_bool
        self.assertTrue(_parse_bool('1'))
        self.assertTrue(_parse_bool('true'))
        self.assertTrue(_parse_bool('TRUE'))
        self.assertTrue(_parse_bool('True'))
        self.assertTrue(_parse_bool('t'))
        self.assertTrue(_parse_bool('yes'))
        self.assertTrue(_parse_bool('YES'))
        self.assertTrue(_parse_bool('y'))
        self.assertTrue(_parse_bool('on'))
        self.assertTrue(_parse_bool('ON'))
        self.assertTrue(_parse_bool('  1  '))
        self.assertTrue(_parse_bool(True))

    def test_false_values(self):
        from config.settings import _parse_bool
        self.assertFalse(_parse_bool('0'))
        self.assertFalse(_parse_bool('false'))
        self.assertFalse(_parse_bool('FALSE'))
        self.assertFalse(_parse_bool('False'))
        self.assertFalse(_parse_bool('f'))
        self.assertFalse(_parse_bool('no'))
        self.assertFalse(_parse_bool('NO'))
        self.assertFalse(_parse_bool('n'))
        self.assertFalse(_parse_bool('off'))
        self.assertFalse(_parse_bool('OFF'))
        self.assertFalse(_parse_bool(''))
        self.assertFalse(_parse_bool('   '))
        self.assertFalse(_parse_bool(False))

    def test_none_uses_default(self):
        from config.settings import _parse_bool
        self.assertFalse(_parse_bool(None))
        self.assertFalse(_parse_bool(None, default=False))
        self.assertTrue(_parse_bool(None, default=True))

    def test_invalid_raises(self):
        from config.settings import _parse_bool
        with self.assertRaises(ValueError):
            _parse_bool('invalid')
        with self.assertRaises(ValueError):
            _parse_bool('2')


class TestParseList(unittest.TestCase):
    def test_comma_separated(self):
        from config.settings import _parse_list
        self.assertEqual(
            _parse_list('a.example.com,b.example.com'),
            ['a.example.com', 'b.example.com']
        )

    def test_strip_whitespace(self):
        from config.settings import _parse_list
        self.assertEqual(
            _parse_list('  a.example.com ,  b.example.com  '),
            ['a.example.com', 'b.example.com']
        )

    def test_drop_empty_items(self):
        from config.settings import _parse_list
        self.assertEqual(
            _parse_list('a.example.com,,b.example.com,,'),
            ['a.example.com', 'b.example.com']
        )
        self.assertEqual(_parse_list(',,,', default=['fallback']), ['fallback'])

    def test_empty_string_uses_default(self):
        from config.settings import _parse_list
        self.assertEqual(_parse_list(''), [])
        self.assertEqual(_parse_list('', default=['a', 'b']), ['a', 'b'])

    def test_none_uses_default(self):
        from config.settings import _parse_list
        self.assertEqual(_parse_list(None), [])
        self.assertEqual(_parse_list(None, default=['x']), ['x'])

    def test_single_item(self):
        from config.settings import _parse_list
        self.assertEqual(_parse_list('.example.com'), ['.example.com'])

    def test_list_input(self):
        from config.settings import _parse_list
        self.assertEqual(
            _parse_list([' a ', '', ' b ']),
            ['a', 'b']
        )
        self.assertEqual(_parse_list(('a', 'b')), ['a', 'b'])


class TestDebugEnvParsing(unittest.TestCase):
    def test_debug_1_is_true(self):
        with mock.patch.dict(os.environ, {'DEBUG': '1'}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertIs(config.settings.DEBUG, True)

    def test_debug_0_is_false(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0'}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertIs(config.settings.DEBUG, False)

    def test_debug_empty_string_is_false(self):
        with mock.patch.dict(os.environ, {'DEBUG': ''}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertIs(config.settings.DEBUG, False)

    def test_debug_default_is_false(self):
        env_copy = os.environ.copy()
        env_copy.pop('DEBUG', None)
        with mock.patch.dict(os.environ, env_copy, clear=True):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertIs(config.settings.DEBUG, False)


class TestAllowedHostsParsing(unittest.TestCase):
    def test_allowed_hosts_comma_list(self):
        with mock.patch.dict(os.environ, {
            'DJANGO_ALLOWED_HOSTS': 'example.com, www.example.com , .foo.com',
            'DEBUG': '0',
        }):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(
                config.settings.ALLOWED_HOSTS,
                ['example.com', 'www.example.com', '.foo.com']
            )

    def test_allowed_hosts_empty_is_empty_list(self):
        with mock.patch.dict(os.environ, {
            'DJANGO_ALLOWED_HOSTS': '',
            'DEBUG': '0',
        }):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(config.settings.ALLOWED_HOSTS, [])


class TestCsrfTrustedOriginsParsing(unittest.TestCase):
    def test_csrf_origins_comma_list(self):
        with mock.patch.dict(os.environ, {
            'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://a.com, https://b.com , https://*.c.com',
            'DEBUG': '0',
        }):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(
                config.settings.CSRF_TRUSTED_ORIGINS,
                ['https://a.com', 'https://b.com', 'https://*.c.com']
            )

    def test_csrf_origins_default_empty(self):
        env_copy = os.environ.copy()
        env_copy.pop('DJANGO_CSRF_TRUSTED_ORIGINS', None)
        env_copy['DEBUG'] = '0'
        with mock.patch.dict(os.environ, env_copy, clear=True):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(config.settings.CSRF_TRUSTED_ORIGINS, [])


class TestProxyAndSecurityConfig(unittest.TestCase):
    def test_proxy_ssl_header_set(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0'}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(
                config.settings.SECURE_PROXY_SSL_HEADER,
                ('HTTP_X_FORWARDED_PROTO', 'https')
            )

    def test_use_x_forwarded_host_enabled(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0'}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertTrue(config.settings.USE_X_FORWARDED_HOST)

    def test_use_x_forwarded_port_enabled(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0'}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertTrue(config.settings.USE_X_FORWARDED_PORT)

    def test_prod_security_flags(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0'}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertTrue(config.settings.SESSION_COOKIE_SECURE)
            self.assertTrue(config.settings.CSRF_COOKIE_SECURE)
            self.assertFalse(config.settings.SECURE_SSL_REDIRECT)
            self.assertTrue(config.settings.SECURE_CONTENT_TYPE_NOSNIFF)

    def test_dev_security_flags_not_overridden(self):
        with mock.patch.dict(os.environ, {'DEBUG': '1'}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertFalse(
                getattr(config.settings, 'SESSION_COOKIE_SECURE', False),
                "SESSION_COOKIE_SECURE should not be forced True in DEBUG mode"
            )
            self.assertFalse(
                getattr(config.settings, 'CSRF_COOKIE_SECURE', False),
                "CSRF_COOKIE_SECURE should not be forced True in DEBUG mode"
            )


if __name__ == '__main__':
    unittest.main()
