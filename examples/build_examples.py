"""Rebuild examples/sample_reports/ from the invented runs in tests/sample_data.py.

    python examples/build_examples.py

No database needed. Run it after changing the rules, the compare or the templates, and commit the result
so the examples match the code.
"""
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "tests"))

import sample_data  # noqa: E402
from convscan import config, report  # noqa: E402
from convscan.runner import load_run  # noqa: E402


def main():
    out = HERE / "sample_reports"
    # Clear old files but keep the folders: synced folders (OneDrive) can refuse to delete a directory.
    for f in out.rglob("*"):
        if f.is_file():
            f.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        pre_dir, post_dir = sample_data.write_runs(tmp)
        cfg = config.load(None)
        cfg["prepared_for"] = "Sample University"
        pre_run, pre = load_run(pre_dir)
        report.render_pre(pre_dir, pre_run, pre, cfg)
        post_run, post = load_run(post_dir)
        report.render_post(post_dir, post_run, post, pre_run, pre, cfg)
        shutil.copytree(pre_dir / "reports", out / "pre", dirs_exist_ok=True)
        shutil.copytree(post_dir / "reports", out / "post", dirs_exist_ok=True)
    print(f"wrote {sum(1 for _ in out.rglob('*.*'))} files in {out}")


if __name__ == "__main__":
    main()
