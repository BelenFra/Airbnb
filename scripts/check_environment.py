import importlib
import os
import sys
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_USE_SHM"] = "0"
os.environ["MPLCONFIGDIR"] = ".cache/matplotlib"
os.environ["XDG_CACHE_HOME"] = ".cache"
os.environ["MPLBACKEND"] = "Agg"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
DIAGNOSTIC_FILE = RESULTS_DIR / "environment_check.txt"


def check_import(module_name: str) -> tuple[bool, str]:
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", "unknown")
        return True, f"{module_name}: OK (version={version})"
    except Exception as exc:
        return False, f"{module_name}: MISSING/ERROR ({exc})"


def check_toolkit() -> tuple[bool, list[str]]:
    messages: list[str] = []
    required_functions = [
        "load_data",
        "load_excel_data",
        "clean_data",
        "create_visualization",
        "split_data",
        "train_xgboost",
        "execute_python_code",
    ]

    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        toolkit = importlib.import_module("mba706_toolkit")
    except Exception as exc:
        return False, [f"mba706_toolkit: MISSING/ERROR ({exc})"]

    messages.append("mba706_toolkit: OK")
    missing = [fn for fn in required_functions if not hasattr(toolkit, fn)]
    if missing:
        return False, messages + [f"mba706_toolkit missing functions: {', '.join(missing)}"]
    return True, messages + ["mba706_toolkit required functions: OK"]


def main() -> None:
    failures: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []

    required_modules = [
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
        "sklearn",
        "scipy",
        "textblob",
        "wordcloud",
        "openpyxl",
        "docx",
        "requests",
        "lxml",
        "html5lib",
    ]

    optional_modules = [
        "xgboost",  # Native build can fail on some systems; toolkit has fallback.
    ]

    checks.append(f"Python executable: {sys.executable}")
    checks.append(f"Python version: {sys.version.split()[0]}")

    for module_name in required_modules:
        ok, msg = check_import(module_name)
        checks.append(msg)
        if not ok:
            failures.append(msg)

    for module_name in optional_modules:
        ok, msg = check_import(module_name)
        checks.append(msg)
        if not ok:
            warnings.append(
                f"{msg} | Note: train_xgboost() should fallback to sklearn backend."
            )

    toolkit_ok, toolkit_msgs = check_toolkit()
    checks.extend(toolkit_msgs)
    if not toolkit_ok:
        failures.extend(toolkit_msgs)

    status = "PASS" if not failures else "FAIL"
    print(status)
    print("Environment check summary:")
    for line in checks:
        print(f"- {line}")
    if warnings:
        print("Warnings:")
        for line in warnings:
            print(f"- {line}")

    if warnings or failures:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(DIAGNOSTIC_FILE, "w", encoding="utf-8") as f:
            f.write(f"Environment check status: {status}\n\n")
            f.write("Checks:\n")
            for line in checks:
                f.write(f"- {line}\n")
            if warnings:
                f.write("\nWarnings:\n")
                for line in warnings:
                    f.write(f"- {line}\n")
            if failures:
                f.write("\nFailures:\n")
                for line in failures:
                    f.write(f"- {line}\n")
        print(f"Diagnostics saved: {DIAGNOSTIC_FILE}")


if __name__ == "__main__":
    main()
