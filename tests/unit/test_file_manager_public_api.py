"""Regression test for Fase 2: FileManager/FileManagerInterface.load_directory().

Replaces main.py's previous direct reach into
self.file_manager.file_manager.directory_loader._load_directory(directory)
(a private-method call three attribute levels deep) with a public
load_directory() method on both FileManager and FileManagerInterface.
"""

from __future__ import annotations

from unittest import mock

import file_manager as fm


def test_file_manager_load_directory_delegates_to_directory_loader():
    manager = fm.FileManager.__new__(fm.FileManager)
    manager.directory_loader = mock.Mock()
    manager.directory_loader._load_directory.return_value = True

    result = manager.load_directory("/some/path")

    assert result is True
    manager.directory_loader._load_directory.assert_called_once_with("/some/path")


def test_file_manager_interface_load_directory_delegates_to_file_manager():
    interface = fm.FileManagerInterface.__new__(fm.FileManagerInterface)
    interface.file_manager = mock.Mock()
    interface.file_manager.load_directory.return_value = False

    result = interface.load_directory("/some/other/path")

    assert result is False
    interface.file_manager.load_directory.assert_called_once_with("/some/other/path")
