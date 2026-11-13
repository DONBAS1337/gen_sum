# -*- coding: utf-8 -*-
"""Regression: Ren'Py 7.4.11 may not expose logging.handlers."""
import builtins
import importlib
import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "don_gen")))


class StrippedRenPyLoggingTest(unittest.TestCase):
    def test_import_without_logging_handlers_and_rotate(self):
        real_import = builtins.__import__

        def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "logging.handlers" or name.startswith("logging.handlers."):
                raise ImportError("No module named handlers")
            return real_import(name, globals, locals, fromlist, level)

        folder = tempfile.mkdtemp(prefix="don-gen-log-test-")
        logger = logging.getLogger("don_gen")
        existing = list(logger.handlers)
        was_setup = getattr(logger, "_don_gen_setup", False)
        try:
            for handler in existing:
                logger.removeHandler(handler)
            logger._don_gen_setup = False

            # Test the exact class of import failure seen in Everlasting Summer.
            sys.modules.pop("dg_runtime", None)
            with mock.patch("builtins.__import__", side_effect=limited_import):
                runtime = importlib.import_module("dg_runtime")
                log = runtime.setup_diagnostics(folder)

            handler = log.handlers[-1]
            handler.max_bytes = 256
            for index in range(80):
                log.info("Player step %03d: location=library", index)
            log.warning("Привет, Совёнок!")
            path = os.path.join(folder, "don_gen.log")
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(os.path.isfile(path + ".1"))
            self.assertTrue(os.path.getsize(path) < 256)
            self.assertLessEqual(len([n for n in os.listdir(folder) if n.startswith("don_gen.log.")]), 3)
            with open(path, "rb") as stream:
                self.assertIn("Совёнок".encode("utf-8"), stream.read())
        finally:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
            for handler in existing:
                logger.addHandler(handler)
            logger._don_gen_setup = was_setup
            shutil.rmtree(folder)


if __name__ == "__main__":
    unittest.main()
