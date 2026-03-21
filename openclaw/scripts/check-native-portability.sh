#!/usr/bin/env bash
# check-native-portability.sh
# Scans native .node binaries for unconditional AVX usage.
# Run after `pnpm install` in CI to catch non-portable native dependencies.

set -euo pipefail

EXIT_CODE=0
echo "Scanning native modules for unconditional AVX instructions..."
echo ""

while IFS= read -r node_file; do
  name=$(echo "$node_file" | sed 's|.*node_modules/||;s|/[^/]*$||')
  
  ymm_count=$(objdump -d "$node_file" 2>/dev/null | grep -c "ymm" || true)
  cpuid_count=$(objdump -d "$node_file" 2>/dev/null | grep -c "cpuid" || true)
  
  if [ "$ymm_count" -gt 0 ] && [ "$cpuid_count" -eq 0 ]; then
    echo "❌ FAIL: $name"
    echo "   $ymm_count AVX instructions, 0 CPUID dispatch calls"
    echo "   This binary will crash on CPUs without AVX support"
    EXIT_CODE=1
  elif [ "$ymm_count" -gt 0 ]; then
    echo "✅ OK:   $name ($ymm_count AVX insns, $cpuid_count CPUID calls)"
  fi
done < <(find node_modules -name "*.node" -path "*linux-x64*" 2>/dev/null | grep -v "rollup\|swc\|musl")

echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "All native modules have proper CPU feature detection."
else
  echo "Some native modules use AVX unconditionally — will crash on non-AVX CPUs."
fi

exit $EXIT_CODE
