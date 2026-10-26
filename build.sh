#!/bin/sh
# Compile the optional C, C++ and Java modules. Run from the project root: sh modules/build.sh
set -e
mkdir -p modules/build
case "$(uname -s)" in
  Darwin) EXT=dylib ;;
  MINGW*|MSYS*|CYGWIN*) EXT=dll ;;
  *) EXT=so ;;
esac
gcc -O2 -shared -fPIC modules/c/risk_core.c -o modules/build/risk_core.$EXT -lm && echo "C module built"
g++ -O2 -shared -fPIC modules/cpp/runoff.cpp -o modules/build/runoff.$EXT && echo "C++ module built"
javac -d modules/build modules/java/ReportGenerator.java && echo "Java module built"
