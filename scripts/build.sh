#!/usr/bin/env bash
# Compile a competitive-programming solution with the debug/sanitizer flags.
#
#   build.sh a          -> compiles a.cpp   into a
#   build.sh a.cpp      -> same
#   build.sh path/to/a  -> works with paths containing spaces
#
# Override the defaults from the environment, e.g.
#   CXX_STD=c++20 build.sh a
#   SANITIZE=0 build.sh a      (turn off asan, for timing runs)

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

if [ $# -lt 1 ]; then
    echo -e "${RED}usage: build.sh <source-or-stem>${NC}" >&2
    exit 2
fi

# Accept either "a" or "a.cpp"; work with the stem from here on.
stem="${1%.cpp}"
src="$stem.cpp"

if [ ! -f "$src" ]; then
    echo -e "${RED}No such file: $src${NC}" >&2
    exit 2
fi

CXX="${CXX:-g++}"
CXX_STD="${CXX_STD:-c++17}"

flags=(
    "-std=$CXX_STD"
    -g -Wall -Wextra -Wconversion -Wshadow
    -D_GLIBCXX_DEBUG -DLSHT_DEBUG
)

# Frame pointers make the sanitizer's stack traces readable.
if [ "${SANITIZE:-1}" != "0" ]; then
    flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer)
fi

if "$CXX" "${flags[@]}" "$src" -lm -o "$stem"; then
    echo -e "${GREEN}Compilation Finished.${NC}"
    exit 0
else
    echo -e "${RED}Compilation Error.${NC}"
    exit 1
fi
