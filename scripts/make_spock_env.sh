#!/usr/bin/env bash
# Create a separate Python environment for the optional SPOCK indicator (exostab check --spock).
#
#   bash make_spock_env.sh [target-folder]        # default: ~/.exostab-spock
#   export EXOSTAB_SPOCK_PYTHON=<target-folder>/bin/python   (Windows: <target-folder>\Scripts\python.exe)
#
# If you installed exostab with pip and have no clone of the repository, download the script first:
#   curl -fsSLO https://raw.githubusercontent.com/mimitoz62/exostab/main/scripts/make_spock_env.sh
#
# SPOCK 2.1.1 needs REBOUND < 5, so it cannot share exostab's environment (DECISIONS.md, D23). SPOCK and the
# packages around it (rebound, reboundx, celmech, xgboost, scikit-learn, safetensors) are pinned to the
# combination tested on 2026-09-28 (macOS arm64, Python 3.12). Their own dependencies (torch, numpy, scipy,
# pandas, ...) are not pinned, so a later run can install newer releases of those. celmech and reboundx are built
# from source, so a C compiler is needed (Xcode command-line tools on macOS, gcc on Linux). On Linux, torch is
# taken from the CPU-only index to avoid about 3 GB of CUDA libraries. On macOS no libomp install is needed: the
# exostab worker uses the copy bundled with scikit-learn. Requires uv (https://docs.astral.sh/uv/).
#
# Running the script again rebuilds the environment from scratch, for example after a failed build. A target
# folder that exists but is not a virtual environment is left alone and the script stops.
set -euo pipefail
target="${1:-$HOME/.exostab-spock}"
if [[ -e "$target" && ! -f "$target/pyvenv.cfg" && -n "$(ls -A "$target")" ]]; then
  echo "error: $target exists and is not a virtual environment; choose another folder." >&2
  exit 1
fi
# UV_VENV_CLEAR=1 replaces an existing environment (current uv refuses to otherwise).
UV_VENV_CLEAR=1 uv venv --python 3.12 "$target"
extra=()
if [[ "$(uname -s)" == "Linux" ]]; then
  extra=(--extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match)
fi
uv pip install --python "$target" ${extra[@]+"${extra[@]}"} \
  "spock==2.1.1" "rebound==4.6.0" "reboundx==4.6.2" "celmech==1.5.8" "xgboost==2.1.4" \
  "scikit-learn==1.5.2" "safetensors==0.4.5" pandas ipython
echo
echo "SPOCK environment ready. Use it with:"
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    # Git Bash on Windows: a venv's interpreter is Scripts\python.exe, and exostab usually runs in PowerShell
    echo "  \$env:EXOSTAB_SPOCK_PYTHON = \"$(cygpath -w "$target")\\Scripts\\python.exe\""
    ;;
  *) echo "  export EXOSTAB_SPOCK_PYTHON=$target/bin/python" ;;
esac
echo "  exostab check \"TRAPPIST-1\" --spock"
