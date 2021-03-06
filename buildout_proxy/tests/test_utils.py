# -*- coding: utf-8 -*-

from buildout_proxy import utils
from unittest import mock

import unittest
import os
import shutil
import requests


class TestUtils(unittest.TestCase):
    @property
    def test_path(self):
        return os.path.join(os.path.abspath("."), ".test_buildout_proxy")

    def setUp(self):
        if not os.path.exists(self.test_path):
            os.mkdir(self.test_path)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @property
    def _fake_request(self):
        """Return a fake request object"""
        return type(
            "request",
            (object,),
            {
                "environ": {"wsgi.url_scheme": "https", "HTTP_HOST": "proxy.be"},
                "matchdict": {
                    "domain": "raw.github.com",
                    "protocol": "https",
                    "path": ("repository", "file.cfg"),
                },
                "registry": type(
                    "registry",
                    (object,),
                    {
                        "settings": {
                            "buildout_proxy.allow.hosts": "*",
                            "buildout_proxy.hosts.passwords": {
                                "affinitic.be": "login:password"
                            },
                            "buildout_proxy.cache": {"default": 300},
                        }
                    },
                )(),
            },
        )()

    def _r_response(self, body, status_code=200):
        return type(
            "response",
            (object,),
            {"status_code": status_code, "content": body.encode("utf8")},
        )()

    def test_compose_url_basic(self):
        request = self._fake_request
        url = utils.compose_url(request)
        self.assertEqual("https://raw.github.com/repository/file.cfg", url)

    def test_compose_url_unallowed_host(self):
        request = self._fake_request
        request.registry.settings["buildout_proxy.allow.hosts"] = "google.com"
        self.assertRaisesRegex(
            ValueError, "Not allowed host .{1,}", utils.compose_url, request
        )

    def test_compose_url_with_password(self):
        request = self._fake_request
        request.matchdict["domain"] = "affinitic.be"
        url = utils.compose_url(request)
        self.assertEqual("https://login:password@affinitic.be/repository/file.cfg", url)

    def test_get_cache_path(self):
        self.assertEqual(
            os.path.join(self.test_path, "acbd18db4cc2f85cedef654fccc4a4d8"),
            utils.get_cache_path(self.test_path, "foo"),
        )

    def test_get_cache_file_not_exist(self):
        pass

    def test_get_cache_file_expired(self):
        pass

    def test_get_cache_file_not_expired(self):
        pass

    def test_get_cache_file_never_expire(self):
        pass

    def test_cache_file(self):
        requests.get = mock.Mock(
            return_value=type(
                "response",
                (object,),
                {
                    "status_code": 200,
                    "content": "[buildout]\ntest = foo\ntest2 = bar".encode("utf8"),
                },
            )()
        )
        f_path = utils.cache_file(
            self._fake_request, "http://foo.bar", os.path.join(self.test_path, "foo")
        )
        with open(f_path, "r") as f:
            self.assertEqual("[buildout]\ntest = foo\ntest2 = bar", f.read())

    def test_cache_file_with_error(self):
        requests.get = mock.Mock(
            return_value=type("response", (object,), {"status_code": 404})()
        )
        f_path = utils.cache_file(
            self._fake_request, "http://foo.bar", os.path.join(self.test_path, "foo")
        )
        self.assertIsNone(f_path)

    def test_cache_file_with_extends(self):
        requests.get = mock.Mock(
            side_effect=(
                self._r_response("[buildout]\nextends =\n  1.cfg\n  2.cfg\n"),
                self._r_response("[part1]\nvar = 1"),
                self._r_response("[part2]\nvar = 2"),
            )
        )
        f_path = utils.cache_file(
            self._fake_request, "http://foo.bar", os.path.join(self.test_path, "foo")
        )
        with open(f_path, "r") as f:
            self.assertEqual(
                (
                    "[buildout]\n"
                    "extends =\n"
                    "  https://proxy.be/r/http/foo.bar/1.cfg\n"
                    "  https://proxy.be/r/http/foo.bar/2.cfg\n"
                ),
                f.read(),
            )

    def test_update_url(self):
        self.assertEqual(
            "https://proxy.be/r/http/affinitic.be/foo/bar.cfg",
            utils.update_url("https://proxy.be", "http://affinitic.be/foo/bar.cfg"),
        )
        self.assertEqual(
            "https://proxy.be/r/https/affinitic.be/foo/bar.cfg",
            utils.update_url("https://proxy.be", "https://affinitic.be/foo/bar.cfg"),
        )

    def test_smart_section_replacer(self):
        text = "test = foo\nextends =\nfoo.cfg\nbar.cfg\nbar = test"
        new_text = utils.smart_section_replacer(
            text, "extends", ["foo.cfg", "bar.cfg"], ["new_foo.cfg", "new_bar.cfg"]
        )
        self.assertEqual(
            "test = foo\nextends =\nnew_foo.cfg\nnew_bar.cfg\nbar = test", new_text
        )
