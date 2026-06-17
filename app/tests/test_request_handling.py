import os
from unittest import mock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('DEBUG', '0')
os.environ.setdefault('DATABASE_URL', 'sqlite://:memory:')
os.environ.setdefault('DJANGO_ALLOWED_HOSTS', '*')
os.environ.setdefault('DJANGO_CSRF_TRUSTED_ORIGINS', '')

import django
django.setup()

from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from django.urls import path


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
from django.urls import re_path

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
        self.assertIn('x_forwarded_proto=https', body)
        self.assertIn('x_forwarded_host=django-traefik.example.com', body)
        self.assertIn('x_forwarded_port=443', body)

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
        from django.conf import settings as s
        original = s.ALLOWED_HOSTS
        from django.test import override_settings
        try:
            s.ALLOWED_HOSTS = ['good.example.com']
            with override_settings(ALLOWED_HOSTS=['good.example.com']):
                response = self.client.get(
                    '/debug/',
                    HTTP_X_FORWARDED_PROTO='https',
                    HTTP_X_FORWARDED_HOST='evil.example.com',
                    HTTP_X_FORWARDED_PORT='443',
                )
                self.assertEqual(response.status_code, 400)
        finally:
            s.ALLOWED_HOSTS = original

    def test_prod_security_headers(self):
        from django.conf import settings as s
        original_debug = s.DEBUG
        try:
            s.DEBUG = False
            s.SESSION_COOKIE_SECURE = True
            s.CSRF_COOKIE_SECURE = True
            s.SECURE_CONTENT_TYPE_NOSNIFF = True
            s.X_FRAME_OPTIONS = 'DENY'

            response = self.client.get(
                '/debug/',
                HTTP_X_FORWARDED_PROTO='https',
                HTTP_X_FORWARDED_HOST='example.com',
                HTTP_X_FORWARDED_PORT='443',
            )
            self.assertEqual(
                response.get('X-Content-Type-Options'),
                'nosniff'
            )
            self.assertEqual(response.get('X-Frame-Options'), 'DENY')
        finally:
            s.DEBUG = original_debug

    def test_dev_mode_no_secure_cookies_forced(self):
        from django.conf import settings as s
        original_debug = s.DEBUG
        original_session = getattr(s, 'SESSION_COOKIE_SECURE', False)
        original_csrf = getattr(s, 'CSRF_COOKIE_SECURE', False)
        try:
            s.DEBUG = True
            s.SESSION_COOKIE_SECURE = False
            s.CSRF_COOKIE_SECURE = False

            self.assertFalse(s.SESSION_COOKIE_SECURE)
            self.assertFalse(s.CSRF_COOKIE_SECURE)
        finally:
            s.DEBUG = original_debug
            s.SESSION_COOKIE_SECURE = original_session
            s.CSRF_COOKIE_SECURE = original_csrf
