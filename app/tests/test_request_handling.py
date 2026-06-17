import os
from unittest import mock

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DEBUG'] = '0'
os.environ['SECRET_KEY'] = 'aB3dE7fG9hJ2kL5mN8pQ1rS4tU6vW0xY2zA5bC8dE1fG4hI7jK0lM3nO6pQr'
os.environ.setdefault('DATABASE_URL', 'sqlite://:memory:')
os.environ['DJANGO_ALLOWED_HOSTS'] = '*'
os.environ.setdefault('DJANGO_CSRF_TRUSTED_ORIGINS', '')
os.environ.setdefault('DJANGO_SECURE_SSL_REDIRECT', '1')
os.environ.setdefault('DJANGO_SECURE_HSTS_SECONDS', '31536000')
os.environ.setdefault('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', '1')
os.environ.setdefault('DJANGO_SECURE_HSTS_PRELOAD', '1')

import django
django.setup()

from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.urls import re_path


def debug_view(request):
    return HttpResponse(
        f"scheme={request.scheme},"
        f"is_secure={request.is_secure()},"
        f"host={request.get_host()},"
        f"port={request.get_port()},"
        f"x_forwarded_proto={request.META.get('HTTP_X_FORWARDED_PROTO', '')},"
        f"x_forwarded_host={request.META.get('HTTP_X_FORWARDED_HOST', '')},"
        f"x_forwarded_port={request.META.get('HTTP_X_FORWARDED_PORT', '')}"
    )


from django.conf import settings

urlpatterns = [
    re_path(r'^debug/$', debug_view),
]
settings.ROOT_URLCONF = 'tests.test_request_handling'


class TestProxyHeaderHandling(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_https_through_x_forwarded_proto(self):
        request = self.factory.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='https',
            HTTP_X_FORWARDED_HOST='example.com',
            HTTP_X_FORWARDED_PORT='443',
        )
        self.assertTrue(request.is_secure())
        self.assertEqual(request.scheme, 'https')

    def test_http_without_forwarded_proto(self):
        request = self.factory.get('/debug/')
        self.assertFalse(request.is_secure())
        self.assertEqual(request.scheme, 'http')

    def test_x_forwarded_proto_http_not_secure(self):
        request = self.factory.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='http',
        )
        self.assertFalse(request.is_secure())
        self.assertEqual(request.scheme, 'http')

    def test_x_forwarded_host_used(self):
        request = self.factory.get(
            '/debug/',
            HTTP_HOST='internal:8000',
            HTTP_X_FORWARDED_HOST='example.com',
            HTTP_X_FORWARDED_PORT='443',
        )
        self.assertEqual(request.get_host(), 'example.com')

    def test_x_forwarded_port_443_for_https(self):
        request = self.factory.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='https',
            HTTP_X_FORWARDED_HOST='example.com',
            HTTP_X_FORWARDED_PORT='443',
        )
        self.assertEqual(request.get_port(), '443')

    def test_end_to_end_view_https_through_proxy(self):
        response = self.client.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='https',
            HTTP_X_FORWARDED_HOST='django-traefik.example.com',
            HTTP_X_FORWARDED_PORT='443',
        )
        body = response.content.decode('utf-8')
        self.assertIn('scheme=https', body)
        self.assertIn('is_secure=True', body)
        self.assertIn('host=django-traefik.example.com', body)
        self.assertIn('port=443', body)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_end_to_end_view_http_dev(self):
        response = self.client.get(
            '/debug/',
            HTTP_HOST='django.localhost:8008',
        )
        body = response.content.decode('utf-8')
        self.assertIn('scheme=http', body)
        self.assertIn('is_secure=False', body)
        self.assertIn('host=django.localhost:8008', body)

    def test_host_validation_allowed_host(self):
        from django.conf import settings as s
        original = s.ALLOWED_HOSTS
        try:
            s.ALLOWED_HOSTS = ['good.example.com']
            response = self.client.get(
                '/debug/',
                HTTP_X_FORWARDED_PROTO='https',
                HTTP_X_FORWARDED_HOST='good.example.com',
                HTTP_X_FORWARDED_PORT='443',
            )
            self.assertEqual(response.status_code, 200)
        finally:
            s.ALLOWED_HOSTS = original

    def test_host_validation_bad_host(self):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=['good.example.com']):
            response = self.client.get(
                '/debug/',
                HTTP_X_FORWARDED_PROTO='https',
                HTTP_X_FORWARDED_HOST='evil.example.com',
                HTTP_X_FORWARDED_PORT='443',
            )
            self.assertEqual(response.status_code, 400)


class TestSSLRedirect(TestCase):
    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_http_request_redirected_to_https(self):
        response = self.client.get(
            '/debug/',
            HTTP_HOST='example.com',
            secure=False,
        )
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].startswith('https://'))

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_proxied_https_request_not_redirected(self):
        response = self.client.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='https',
            HTTP_X_FORWARDED_HOST='example.com',
            HTTP_X_FORWARDED_PORT='443',
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_proxied_http_request_redirected(self):
        response = self.client.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='http',
            HTTP_HOST='example.com',
        )
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].startswith('https://'))


class TestHSTSHeaders(TestCase):
    @override_settings(
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_hsts_header_present_on_https_response(self):
        response = self.client.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='https',
            HTTP_X_FORWARDED_HOST='example.com',
            HTTP_X_FORWARDED_PORT='443',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Strict-Transport-Security'], 'max-age=31536000; includeSubDomains; preload')

    @override_settings(
        SECURE_HSTS_SECONDS=0,
        SECURE_SSL_REDIRECT=False,
    )
    def test_hsts_header_absent_when_disabled(self):
        response = self.client.get(
            '/debug/',
            HTTP_HOST='example.com',
        )
        self.assertFalse(response.has_header('Strict-Transport-Security'))


class TestSecurityHeaders(TestCase):
    @override_settings(
        SECURE_CONTENT_TYPE_NOSNIFF=True,
        X_FRAME_OPTIONS='DENY',
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_prod_security_headers(self):
        response = self.client.get(
            '/debug/',
            HTTP_X_FORWARDED_PROTO='https',
            HTTP_X_FORWARDED_HOST='example.com',
            HTTP_X_FORWARDED_PORT='443',
        )
        self.assertEqual(response.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(response.get('X-Frame-Options'), 'DENY')

    @override_settings(
        DEBUG=True,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=0,
    )
    def test_dev_mode_no_secure_cookies_forced(self):
        from django.conf import settings as s
        self.assertFalse(s.SESSION_COOKIE_SECURE)
        self.assertFalse(s.CSRF_COOKIE_SECURE)
