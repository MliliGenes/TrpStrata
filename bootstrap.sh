#!/usr/bin/env bash
# Download and install the latest trpStrata without a Git checkout.
set -euo pipefail

main() {
	case "${1:-}" in
		--no-start|"") ;;
		-h|--help) echo "Usage: bash bootstrap.sh [--no-start]"; return 0 ;;
		*) echo "Usage: bash bootstrap.sh [--no-start]" >&2; return 1 ;;
	esac
	if [ "$#" -gt 1 ]; then
		echo "Usage: bash bootstrap.sh [--no-start]" >&2
		return 1
	fi
	for tool in curl tar mktemp; do
		command -v "$tool" >/dev/null || { echo "Required command not found: $tool" >&2; return 1; }
	done

	WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/trpstrata.XXXXXXXX")
	trap 'rm -rf -- "$WORK_DIR"' EXIT
	trap 'exit 130' INT
	trap 'exit 143' TERM
	echo "Downloading the latest trpStrata…"
	curl -fSL --retry 3 https://codeload.github.com/MliliGenes/TrpStrata/tar.gz/refs/heads/main \
		-o "$WORK_DIR/source.tar.gz"
	mkdir "$WORK_DIR/source"
	tar -xzf "$WORK_DIR/source.tar.gz" -C "$WORK_DIR/source" --strip-components=1
	bash "$WORK_DIR/source/install.sh" "$@"
}

main "$@"
