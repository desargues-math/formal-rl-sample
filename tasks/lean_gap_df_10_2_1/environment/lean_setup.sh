#!/usr/bin/env bash
# Shared agent/verifier image for the two selected Lean tasks.
# Follow LeanEval's split tool build: Comparator uses its own Lean 4.34.0;
# lean4export uses the exact 4.35.0-rc3 toolchain of the submitted .olean files.
# Only Mathlib and its locked dependencies are installed as solution libraries.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

LEAN_TOOLCHAIN=$(cat /opt/build/lean-toolchain)
COMPARATOR_TOOLCHAIN=leanprover/lean4:v4.34.0
COMPARATOR_REV=d03acab154d269c06e60e4de7e4cc85deebff94b
EXPORTER_REV=076e8e57707e813375e8f9da8bf989799ace9680
LANDRUN_REV=5ed4a3db3a4ad930d577215c6b9abaa19df7f99f
GO_VERSION=1.25.12

apt-get update -qq
apt-get install -y -qq --no-install-recommends git curl ca-certificates build-essential xz-utils \
  zstd python3 procps iproute2 iptables tmux >/dev/null
rm -rf /var/lib/apt/lists/*
git config --system --add safe.directory '*'

export ELAN_HOME=/opt/elan PATH=/opt/elan/bin:$PATH
curl --retry 3 --retry-all-errors --retry-delay 5 -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -o /tmp/elan-init.sh
sh /tmp/elan-init.sh -y --default-toolchain "$LEAN_TOOLCHAIN" --no-modify-path
rm /tmp/elan-init.sh
# Large toolchain archives can hit transient network timeouts. Install both
# explicitly, with bounded retries, before invoking their build tools.
install_toolchain() {
  local attempt
  for attempt in 1 2 3; do
    if elan toolchain install "$1"; then return 0; fi
    if [ "$attempt" -lt 3 ]; then sleep 5; fi
  done
  return 1
}
install_toolchain "$LEAN_TOOLCHAIN"
install_toolchain "$COMPARATOR_TOOLCHAIN"

# Both production linux/amd64 and local linux/arm64 image builds use the same pins.
case "$(dpkg --print-architecture)" in
  amd64) go_arch=amd64 ;;
  arm64) go_arch=arm64 ;;
  *) echo 'Only amd64 and arm64 image builds are supported' >&2; exit 1 ;;
esac
curl --retry 3 --retry-all-errors --retry-delay 5 -sSfL "https://go.dev/dl/go${GO_VERSION}.linux-${go_arch}.tar.gz" | tar -C /tmp -xz
GOBIN=/usr/local/bin GOPATH=/tmp/gopath GOCACHE=/tmp/gocache \
  /tmp/go/bin/go install "github.com/zouuup/landrun/cmd/landrun@${LANDRUN_REV}"
rm -rf /tmp/go /tmp/gopath /tmp/gocache

# Comparator's source pin is shared with FineEnvs. Preserve FineEnvs' thread
# allowlist patch so nested Lake builds obey the sandbox's resource allocation.
git clone -q https://github.com/leanprover/comparator.git /tmp/comparator
(
  cd /tmp/comparator
  git checkout -q "$COMPARATOR_REV"
  test "$(cat lean-toolchain)" = "$COMPARATOR_TOOLCHAIN"
  sed -i 's/envPass := #\["PATH", "HOME", "LEAN_ABORT_ON_PANIC"\]/envPass := #["PATH", "HOME", "LEAN_ABORT_ON_PANIC", "LEAN_NUM_THREADS"]/; s/envPass := #\["PATH", "HOME", "LEAN_PATH", "LEAN_ABORT_ON_PANIC"\]/envPass := #["PATH", "HOME", "LEAN_PATH", "LEAN_ABORT_ON_PANIC", "LEAN_NUM_THREADS"]/' Main.lean
  test "$(grep -c '"LEAN_NUM_THREADS"' Main.lean)" -eq 2
  lake build comparator
  install -m 0755 .lake/build/bin/comparator /usr/local/bin/comparator
)
rm -rf /tmp/comparator

# The exporter reads .olean files, so its build toolchain must match the tasks.
git clone -q https://github.com/leanprover/lean4export.git /tmp/lean4export
(
  cd /tmp/lean4export
  git checkout -q "$EXPORTER_REV"
  printf '%s\n' "$LEAN_TOOLCHAIN" > lean-toolchain
  lake build lean4export
  install -m 0755 .lake/build/bin/lean4export /usr/local/bin/lean4export
)
rm -rf /tmp/lean4export

# A single, locked Mathlib-only package tree is shared read-only by agent and
# verifier projects. Fetch exact manifest revisions without re-resolving Lake.
mkdir -p /opt/lean-env/.lake/packages
cd /opt/lean-env
cp /opt/build/lakefile.lean /opt/build/lake-manifest.json /opt/build/lean-toolchain .
runtime_prefix=$(lean --print-prefix)
printf '%s\n' "$runtime_prefix/bin" > toolchain-bin
python3 - <<'PY'
import json
import subprocess
from pathlib import Path

manifest = json.loads(Path("lake-manifest.json").read_text())
for package in manifest["packages"]:
    dest = f".lake/packages/{package['name']}"
    subprocess.run(["git", "init", "-q", dest], check=True)
    subprocess.run(["git", "-C", dest, "remote", "add", "origin", package["url"]], check=True)
    subprocess.run(["git", "-C", dest, "fetch", "-q", "--depth", "1", "origin", package["rev"]], check=True)
    subprocess.run(["git", "-C", dest, "checkout", "-q", "FETCH_HEAD"], check=True)
PY

# Build the cache executable before removing native-link-only files. Keep both
# toolchains' shared libraries, .olean and interpreter files: Comparator and the
# exporter use different Lean runtimes, and native-link assumptions are checked
# below with ldd after pruning. No .so/.olean/.ir output is truncated.
lake exe cache --help >/dev/null
find /opt/elan/toolchains -path '*/lib/*' -name '*.a' -type f -delete
find /opt/elan/toolchains -path '*/lib/libLLVM*' -type f -delete
find /opt/elan/toolchains -path '*/lib/libclang-cpp*' -type f -delete
mapfile -t build_packages < <(dpkg-query -W -f '${binary:Package}\n' build-essential 'gcc-13*' 'g++-13*' \
  'cpp-13*' 'libstdc++-13-dev*' 'libgcc-13-dev*' 2>/dev/null || true)
if ((${#build_packages[@]})); then
  apt-get purge -y -qq "${build_packages[@]}" >/dev/null
  apt-get autoremove -y -qq >/dev/null
fi
for binary in /usr/local/bin/comparator /usr/local/bin/lean4export "$runtime_prefix/bin/lean" "$runtime_prefix/bin/lake"; do
  ldd "$binary" > /tmp/native-libraries.txt
  if grep -q 'not found' /tmp/native-libraries.txt; then
    cat /tmp/native-libraries.txt >&2
    echo "Missing runtime library for $binary" >&2
    exit 1
  fi
done
rm -f /tmp/native-libraries.txt
bash /opt/build/fetch_mathlib.sh
rm -f /opt/lean-env/.lake/packages/mathlib/.lake/build/bin/cache

# Task inputs are local build-context files produced by the adapter. There is
# no network fetch of OpenAI or Annals source code during image construction.
test "$(find /opt/annals-challenge/tasks -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 2
install -m 0755 /opt/build/pack_submission.py /opt/annals-challenge/pack_submission.py
install -m 0755 /opt/build/start_task.py /opt/annals-challenge/start_task.py

# Agent projects are initialized on demand by start_task.py. A pristine verifier
# independently stages trusted files; no agent-owned Lake files cross into it.
mkdir -p /workspace/.lake
cp /opt/lean-env/lakefile.lean /opt/lean-env/lake-manifest.json /opt/lean-env/lean-toolchain /workspace/
ln -s /opt/lean-env/.lake/packages /workspace/.lake/packages
useradd --uid 2000 --create-home --shell /usr/sbin/nologin grader
mkdir -p /var/lib/annals-grade
chmod 0711 /var/lib/annals-grade

# Infrastructure-only smoke check: import the installed library, then ensure
# the warm cache needs no dependency rebuilding. This does not attempt any of
# the supplied research theorem or require any reference proofs.
cd /workspace
printf 'import Mathlib\n\ndef environmentSmoke : Nat := 0\n' > Submission.lean
lake build Submission
printf '\n-- warm-cache check\n' >> Submission.lean
lake build Submission 2>&1 | tee /tmp/smoke.log
if grep 'Built' /tmp/smoke.log | grep -qv 'Built Submission'; then
  echo 'The prebuilt Mathlib is incomplete: a second build still compiled dependencies' >&2
  exit 1
fi
rm -rf Submission.lean .lake/build /tmp/smoke.log

# Cache downloads can be 0600. The grader needs read access to both toolchains
# and the package tree while they remain root-owned and not group-writable.
chmod -R a+rX,go-w /opt/elan /opt/lean-env /opt/annals-challenge
smoke_dir=$(mktemp -d /var/lib/annals-grade/smoke.XXXX)
cp /opt/lean-env/lakefile.lean /opt/lean-env/lake-manifest.json /opt/lean-env/lean-toolchain "$smoke_dir/"
mkdir "$smoke_dir/.lake"
ln -s /opt/lean-env/.lake/packages "$smoke_dir/.lake/packages"
printf 'import Mathlib\n\ndef environmentSmoke : Nat := 0\n' > "$smoke_dir/Submission.lean"
chmod 0755 "$smoke_dir"
chown grader "$smoke_dir/.lake"
(cd "$smoke_dir" && runuser -u grader -- env -i \
  PATH="$runtime_prefix/bin:/usr/local/bin:/usr/bin:/bin" HOME="$smoke_dir" LEAN_NUM_THREADS=2 \
  lake build Submission) 2>&1 | tee /tmp/smoke.log
if grep 'Built' /tmp/smoke.log | grep -qv 'Built Submission' || ! grep -q 'Build completed successfully' /tmp/smoke.log; then
  echo 'The grader user cannot build against the prebuilt Mathlib' >&2
  exit 1
fi
rm -rf "$smoke_dir" /tmp/smoke.log /opt/build /root/.cache
df -h /
du -sh /opt/elan /opt/lean-env /opt/annals-challenge
