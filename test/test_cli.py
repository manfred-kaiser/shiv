import subprocess
import sys
import tempfile

from pathlib import Path

import pytest

from click.testing import CliRunner

from shiv.cli import main, validate_interpreter, map_shared_objects
from shiv.constants import DISALLOWED_PIP_ARGS, NO_PIP_ARGS, NO_OUTFILE, BLACKLISTED_ARGS


def strip_header(output):
    return '\n'.join(output.splitlines()[1:])


class TestCLI:
    @pytest.fixture
    def runner(self):
        return lambda args: CliRunner().invoke(main, args)

    def test_no_args(self, runner):
        result = runner([])
        assert result.exit_code == 1
        assert strip_header(result.output) == NO_PIP_ARGS

    def test_no_outfile(self, runner):
        result = runner(['-e', 'test', 'flask'])
        assert result.exit_code == 1
        assert strip_header(result.output) == NO_OUTFILE

    @pytest.mark.parametrize("arg", [arg for tup in BLACKLISTED_ARGS.keys() for arg in tup])
    def test_blacklisted_args(self, runner, arg):
        result = runner(['-o', 'tmp', arg])

        # get the 'reason' message:
        for tup in BLACKLISTED_ARGS:
            if arg in tup:
                reason = BLACKLISTED_ARGS[tup]

        assert result.exit_code == 1

        # assert we got the correct reason
        assert strip_header(result.output) == DISALLOWED_PIP_ARGS.format(arg=arg, reason=reason)

    def test_hello_world(self, tmpdir, runner, package_location):
        with tempfile.TemporaryDirectory(dir=tmpdir) as tmpdir:
            output_file = Path(tmpdir, 'test.pyz').as_posix()

            result = runner(['-e', 'hello:main', '-o', output_file, package_location])

            # ensure the created file actually exists
            assert Path(output_file).exists()

            # check that the command successfully completed
            assert result.exit_code == 0

            # now run the produced zipapp
            with subprocess.Popen([output_file], stdout=subprocess.PIPE) as proc:
                assert proc.stdout.read().decode() == 'hello world\n'

    def test_interpreter(self):
        assert validate_interpreter(None) == validate_interpreter() == f'/usr/bin/env {Path(sys.executable).name}'

        with pytest.raises(SystemExit):
            validate_interpreter('/usr/local/bogus_python')

    @pytest.mark.skipif(len(sys.executable) > 128, reason='only run this test is the shebang is not too long')
    def test_real_interpreter(self):
        assert validate_interpreter(sys.executable) == sys.executable

    def test_so_map(self, sp):
        assert map_shared_objects(sp) == {
            'fake_c_extension._extern': 'fake_c_extension/_extern.cpython-36m-x86_64-linux-gnu.so',
            'other_fake_c_extension_darwin.foobar': 'other_fake_c_extension_darwin/foobar.cpython-36m-darwin.so',
        }