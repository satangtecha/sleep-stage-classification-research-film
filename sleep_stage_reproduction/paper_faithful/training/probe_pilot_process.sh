#!/bin/sh
set -eu

run_id=${1:?run ID is required}
for pid in $(pgrep -x python 2>/dev/null || true); do
    command_line=$(tr '\000' ' ' < "/proc/$pid/cmdline")
    case "$command_line" in
        *"paper_faithful.training.cli pilot"*"$run_id"*|*"paper_faithful.training.cli multi-seed-pilot"*"$run_id"*)
            echo "PID=$pid"
            awk '/^rchar:/ { print "RCHAR=" $2 }' "/proc/$pid/io"
            awk '{ print "CPU_TICKS=" $14 + $15 }' "/proc/$pid/stat"
            attempts=0
            while [ "$attempts" -lt 50 ]; do
                for descriptor in "/proc/$pid/fd/"*; do
                    path=$(readlink "$descriptor" 2>/dev/null || true)
                    case "$path" in
                        /mnt/e/*)
                            echo "OPEN=$path"
                            exit 0
                            ;;
                    esac
                done
                attempts=$((attempts + 1))
                sleep 0.1
            done
            exit 0
            ;;
    esac
done
echo 'PILOT_MISSING=1'
