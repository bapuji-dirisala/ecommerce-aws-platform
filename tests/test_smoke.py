"""Phase 0 smoke tests — the package imports and the CLI responds."""

from __future__ import annotations

import subprocess
import sys


def test_package_imports() -> None:
    import ecom_aws

    assert ecom_aws.__version__


def test_cli_version_flag(capsys) -> None:
    from ecom_aws.cli import main

    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "ecom-aws" in out


def test_cli_version_subcommand() -> None:
    from ecom_aws import __version__
    from ecom_aws.cli import main

    rc = main(["version"])
    assert rc == 0
    assert __version__


def test_cli_no_args_prints_help(capsys) -> None:
    from ecom_aws.cli import main

    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "usage:" in out.lower()


def test_entry_point_script_installed() -> None:
    rc = subprocess.run(
        [sys.executable, "-m", "ecom_aws.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 0
    assert "ecom-aws" in rc.stdout
