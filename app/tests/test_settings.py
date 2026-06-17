import os
import unittest
from unittest import mock

_VALID_SECRET_KEY = 'aB3dE7fG9hJ2kL5mN8pQ1rS4tU6vW0xY2zA5bC8dE1fG4hI7jK0lM3nO6pQr'


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


class TestParseInt(unittest.TestCase):
    def test_valid_integers(self):
        from config.settings import _parse_int
        self.assertEqual(_parse_int('0'), 0)
        self.assertEqual(_parse_int('31536000'), 31536000)
        self.assertEqual(_parse_int('  42  '), 42)
        self.assertEqual(_parse_int(42), 42)

    def test_none_uses_default(self):
        from config.settings import _parse_int
        self.assertEqual(_parse_int(None), 0)
        self.assertEqual(_parse_int(None, default=99), 99)

    def test_invalid_returns_default(self):
        from config.settings import _parse_int
        self.assertEqual(_parse_int('abc'), 0)
        self.assertEqual(_parse_int('abc', default=99), 99)
        self.assertEqual(_parse_int('', default=7), 7)


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
        with mock.patch.dict(os.environ, {'DEBUG': '1', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertIs(config.settings.DEBUG, True)

    def test_debug_0_is_false(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertIs(config.settings.DEBUG, False)

    def test_debug_empty_string_is_false(self):
        with mock.patch.dict(os.environ, {'DEBUG': '', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertIs(config.settings.DEBUG, False)

    def test_debug_default_is_false(self):
        env_copy = os.environ.copy()
        env_copy.pop('DEBUG', None)
        env_copy['SECRET_KEY'] = _VALID_SECRET_KEY
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
            'SECRET_KEY': _VALID_SECRET_KEY,
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
            'SECRET_KEY': _VALID_SECRET_KEY,
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
            'SECRET_KEY': _VALID_SECRET_KEY,
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
        env_copy['SECRET_KEY'] = _VALID_SECRET_KEY
        with mock.patch.dict(os.environ, env_copy, clear=True):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(config.settings.CSRF_TRUSTED_ORIGINS, [])


class TestSecretKeyValidation(unittest.TestCase):
    def test_django_insecure_prefix_rejected_in_prod(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '0',
            'SECRET_KEY': 'django-insecure-abcdefg1234567890abcdefghijkl',
        }):
            import importlib
            import config.settings
            from django.core.exceptions import ImproperlyConfigured
            with self.assertRaises(ImproperlyConfigured) as ctx:
                importlib.reload(config.settings)
            self.assertIn('SECRET_KEY is not safe', str(ctx.exception))

    def test_placeholder_change_me_rejected_in_prod(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '0',
            'SECRET_KEY': 'change-me-to-a-long-random-string-please-change-me-now',
        }):
            import importlib
            import config.settings
            from django.core.exceptions import ImproperlyConfigured
            with self.assertRaises(ImproperlyConfigured) as ctx:
                importlib.reload(config.settings)
            self.assertIn('SECRET_KEY is not safe', str(ctx.exception))

    def test_short_key_rejected_in_prod(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '0',
            'SECRET_KEY': 'tooshort',
        }):
            import importlib
            import config.settings
            from django.core.exceptions import ImproperlyConfigured
            with self.assertRaises(ImproperlyConfigured):
                importlib.reload(config.settings)

    def test_low_entropy_key_rejected_in_prod(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '0',
            'SECRET_KEY': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        }):
            import importlib
            import config.settings
            from django.core.exceptions import ImproperlyConfigured
            with self.assertRaises(ImproperlyConfigured):
                importlib.reload(config.settings)

    def test_valid_key_accepted_in_prod(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '0',
            'SECRET_KEY': 'aB3dE7fG9hJ2kL5mN8pQ1rS4tU6vW0xY2zA5bC8dE1fG4hI7jK0lM3nO6pQr',
        }):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(
                config.settings.SECRET_KEY,
                'aB3dE7fG9hJ2kL5mN8pQ1rS4tU6vW0xY2zA5bC8dE1fG4hI7jK0lM3nO6pQr'
            )

    def test_insecure_key_allowed_in_dev(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '1',
            'SECRET_KEY': 'django-insecure-*y(bpj*0ho*d6w9_cz0fvf428$&&jyzw==ztb$0(fkbvq)o-r5',
        }):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertTrue(config.settings.DEBUG)


class TestProxyAndSecurityConfig(unittest.TestCase):
    def test_proxy_ssl_header_set(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(
                config.settings.SECURE_PROXY_SSL_HEADER,
                ('HTTP_X_FORWARDED_PROTO', 'https')
            )

    def test_use_x_forwarded_host_enabled(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertTrue(config.settings.USE_X_FORWARDED_HOST)

    def test_use_x_forwarded_port_enabled(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertTrue(config.settings.USE_X_FORWARDED_PORT)

    def test_prod_security_flags(self):
        with mock.patch.dict(os.environ, {'DEBUG': '0', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertTrue(config.settings.SESSION_COOKIE_SECURE)
            self.assertTrue(config.settings.CSRF_COOKIE_SECURE)
            self.assertTrue(config.settings.SECURE_SSL_REDIRECT)
            self.assertTrue(config.settings.SECURE_CONTENT_TYPE_NOSNIFF)
            self.assertEqual(config.settings.SECURE_HSTS_SECONDS, 31536000)
            self.assertTrue(config.settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
            self.assertTrue(config.settings.SECURE_HSTS_PRELOAD)
            self.assertEqual(config.settings.X_FRAME_OPTIONS, 'DENY')

    def test_prod_ssl_redirect_can_be_disabled_via_env(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '0',
            'SECRET_KEY': _VALID_SECRET_KEY,
            'DJANGO_SECURE_SSL_REDIRECT': '0',
        }):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertFalse(config.settings.SECURE_SSL_REDIRECT)

    def test_prod_hsts_seconds_overridable_via_env(self):
        with mock.patch.dict(os.environ, {
            'DEBUG': '0',
            'SECRET_KEY': _VALID_SECRET_KEY,
            'DJANGO_SECURE_HSTS_SECONDS': '60',
        }):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertEqual(config.settings.SECURE_HSTS_SECONDS, 60)

    def test_dev_security_flags_disabled(self):
        with mock.patch.dict(os.environ, {'DEBUG': '1', 'SECRET_KEY': _VALID_SECRET_KEY}):
            import importlib
            import config.settings
            importlib.reload(config.settings)
            self.assertFalse(config.settings.SESSION_COOKIE_SECURE)
            self.assertFalse(config.settings.CSRF_COOKIE_SECURE)
            self.assertFalse(config.settings.SECURE_SSL_REDIRECT)
            self.assertEqual(config.settings.SECURE_HSTS_SECONDS, 0)
            self.assertFalse(config.settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
            self.assertFalse(config.settings.SECURE_HSTS_PRELOAD)


if __name__ == '__main__':
    unittest.main()
