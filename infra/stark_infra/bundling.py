import shutil
import subprocess
import sys
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, ILocalBundling
from aws_cdk import aws_lambda as lambda_


@jsii.implements(ILocalBundling)
class _LocalPythonBundling:
    """Bundles the Lambda deployment package on the host, without Docker.

    Safe here because starkbank and its transitive dependencies are pure
    Python (no compiled extensions), so a package built on the deploy
    machine (Windows/macOS/Linux) also runs correctly on Lambda's Linux
    runtime.
    """

    def __init__(self, project_root: Path):
        self._project_root = project_root

    def try_bundle(self, output_dir: str, *args, **kwargs) -> bool:
        requirements = self._project_root / "requirements.txt"
        output_path = Path(output_dir)

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements), "-t", str(output_path)],
            check=True,
        )
        shutil.copytree(
            self._project_root / "src",
            output_path / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        return True


def python_lambda_code(project_root: Path) -> lambda_.Code:
    # The asset path is scoped to src/ only (never the project root) so that
    # files like privateKey.pem, .git or .venv can never end up hashed into
    # or copied inside the Lambda deployment package.
    return lambda_.Code.from_asset(
        str(project_root / "src"),
        exclude=["__pycache__", "*.pyc"],
        bundling=BundlingOptions(
            # Only used as a required-field placeholder: local bundling below
            # always succeeds for this project (starkbank has no compiled
            # dependencies), so this Docker image is never actually run.
            image=lambda_.Runtime.PYTHON_3_13.bundling_image,
            local=_LocalPythonBundling(project_root),
        ),
    )
