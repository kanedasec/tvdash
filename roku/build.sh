#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
output_file=${1:-"$project_dir/tvdash-roku.zip"}
config_file=${TVDASH_ROKU_CONFIG:-"$script_dir/source/config.brs"}

use_environment=false
if [ -n "${TVDASH_BASE_URL:-}" ] || [ -n "${TVDASH_ROKU_API_KEY:-}" ]; then
    if [ -z "${TVDASH_BASE_URL:-}" ] || [ -z "${TVDASH_ROKU_API_KEY:-}" ]; then
        echo "Set both TVDASH_BASE_URL and TVDASH_ROKU_API_KEY." >&2
        exit 1
    fi
    if ! printf '%s' "$TVDASH_BASE_URL" | grep -Eq '^https://[A-Za-z0-9.-]+(:[0-9]+)?$'; then
        echo "TVDASH_BASE_URL must be an HTTPS origin without a path." >&2
        exit 1
    fi
    if ! printf '%s' "$TVDASH_ROKU_API_KEY" | grep -Eq '^[A-Za-z0-9_-]{32,128}$'; then
        echo "TVDASH_ROKU_API_KEY must contain 32-128 URL-safe characters." >&2
        exit 1
    fi
    use_environment=true
elif [ ! -f "$config_file" ]; then
    echo "No private Roku configuration supplied." >&2
    echo "Set TVDASH_BASE_URL and TVDASH_ROKU_API_KEY, or create roku/source/config.brs." >&2
    exit 1
fi

if [ "$use_environment" = false ] && grep -q "replace-with-the-same-roku-api-key" "$config_file"; then
    echo "Refusing to build with the placeholder Roku API key." >&2
    exit 1
fi

temporary_dir=$(mktemp -d)
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
temporary_zip="$temporary_dir/tvdash-roku.zip"
package_dir="$temporary_dir/package"

mkdir -p "$package_dir/source"
cp "$script_dir/manifest" "$package_dir/manifest"
cp "$script_dir/source/main.brs" "$package_dir/source/main.brs"
cp -R "$script_dir/components" "$package_dir/components"

if [ "$use_environment" = true ]; then
    {
        printf 'Function TvdashBaseUrl() as String\n'
        printf '    return "%s"\n' "$TVDASH_BASE_URL"
        printf 'End Function\n\n'
        printf 'Function TvdashApiKey() as String\n'
        printf '    return "%s"\n' "$TVDASH_ROKU_API_KEY"
        printf 'End Function\n'
    } > "$package_dir/source/config.brs"
else
    cp "$config_file" "$package_dir/source/config.brs"
fi

if [ -d "$script_dir/images" ]; then
    cp -R "$script_dir/images" "$package_dir/images"
fi

set -- manifest source components
if [ -d "$package_dir/images" ]; then
    set -- "$@" images
fi

(cd "$package_dir" && zip -qr "$temporary_zip" "$@")

mv -- "$temporary_zip" "$output_file"
echo "Created $output_file"
