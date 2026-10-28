# One image for both sample tasks and their separate verifier sandboxes.
FROM ubuntu:24.04
ENV ELAN_HOME=/opt/elan \
    PATH=/opt/elan/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 \
    LEAN_NUM_THREADS=3
COPY lean_setup.sh fetch_mathlib.sh lakefile.lean lake-manifest.json lean-toolchain pack_submission.py start_task.py /opt/build/
COPY challenges/ /opt/annals-challenge/tasks/
RUN bash /opt/build/lean_setup.sh
WORKDIR /workspace
