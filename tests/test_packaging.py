"""Packaging scripts: the properties whose absence silently broke a build.

Each test here maps to a real defect found by running the artefacts:
- the two PyInstaller entry points drifting apart,
- the uninstaller looking somewhere else than the installer,
- the bundle copy dereferencing symlinks and doubling a 200 MB library.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_deb  # noqa: E402
import build_desktop  # noqa: E402
import build_linux_bundle  # noqa: E402
import install_linux  # noqa: E402
import uninstall_linux  # noqa: E402


def test_both_builders_share_the_same_pyinstaller_options():
    assert build_desktop.common_args is build_linux_bundle.common_args


def test_bundle_embeds_the_qt_window_engine():
    args = build_linux_bundle.common_args()
    assert "webview.platforms.qt" in args
    assert "PySide6.QtWebEngineWidgets" in args


def test_schema_is_shipped_into_a_directory_not_onto_a_file():
    # `--add-data src:app/db/schema.sql` made PyInstaller create a directory
    # named schema.sql, and the frozen app died on import.
    args = build_linux_bundle.common_args()
    schema = [a for a in args if a.endswith("schema.sql:app/db")]
    assert schema, args


@pytest.mark.parametrize(
    "resolver",
    ["install_dir", "applications_dir", "icons_dir", "bin_dir"],
)
def test_uninstaller_resolves_paths_exactly_like_the_installer(resolver):
    assert getattr(uninstall_linux, resolver) is getattr(install_linux, resolver)


def test_installer_honours_xdg_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_BIN_HOME", str(tmp_path / "bin"))
    assert install_linux.install_dir() == tmp_path / "data" / "llm-cockpit"
    assert install_linux.bin_dir() == tmp_path / "bin"
    assert install_linux.applications_dir() == tmp_path / "data" / "applications"


def test_deb_depends_are_declared():
    # QtWebEngine needs system libraries the bundle does not carry.
    assert "libnss3" in build_deb.RUNTIME_DEPENDS
    assert any(d.startswith("libasound2") for d in build_deb.RUNTIME_DEPENDS)


def test_deb_copy_preserves_symlinks():
    # copytree() without symlinks=True dereferenced libQt6WebEngineCore.so.6
    # and shipped 200 MB twice.
    source = (SCRIPTS / "build_deb.py").read_text(encoding="utf-8")
    assert "copytree(bundle, target, symlinks=True)" in source
    source = (SCRIPTS / "install_linux.py").read_text(encoding="utf-8")
    assert "copytree(BUNDLE, app_bin, symlinks=True)" in source
