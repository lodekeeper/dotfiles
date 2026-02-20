#!/usr/bin/env node

import {spawn} from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const DEFAULT_BASE_FALLBACK = "origin/unstable";
const DEFAULT_MAX_PACKAGES = 8;
const ROOT_DIR = process.cwd();
const PACKAGES_DIR = path.join(ROOT_DIR, "packages");

const COLOR = {
  reset: "\x1b[0m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  gray: "\x1b[90m",
  bold: "\x1b[1m",
};

const ICON = {
  start: "🚀",
  step: "🧭",
  ok: "✅",
  fail: "❌",
  warn: "⚠️",
  info: "ℹ️",
  time: "⏱️",
  skip: "⏭️",
};

function paint(color, text) {
  return `${COLOR[color]}${text}${COLOR.reset}`;
}

function formatMs(ms) {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function parseArgs(argv) {
  /** @type {{
   * quick: boolean;
   * strict: boolean;
   * base: string | null;
   * all: boolean;
   * dryRun: boolean;
   * ciOrder: boolean;
   * maxPackages: number;
   * noFetch: boolean;
   * verbose: boolean;
   * help: boolean;
   * }}
   */
  const flags = {
    quick: false,
    strict: true,
    base: null,
    all: false,
    dryRun: false,
    ciOrder: false,
    maxPackages: DEFAULT_MAX_PACKAGES,
    noFetch: false,
    verbose: false,
    help: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    switch (arg) {
      case "--quick":
        flags.quick = true;
        flags.strict = false;
        break;
      case "--strict":
        flags.strict = true;
        flags.quick = false;
        break;
      case "--base":
        if (i + 1 >= argv.length) {
          throw new Error("Missing value for --base");
        }
        flags.base = argv[i + 1];
        i++;
        break;
      case "--all":
        flags.all = true;
        break;
      case "--dry-run":
        flags.dryRun = true;
        break;
      case "--ci-order":
        flags.ciOrder = true;
        break;
      case "--max-packages": {
        if (i + 1 >= argv.length) {
          throw new Error("Missing value for --max-packages");
        }
        const parsed = Number.parseInt(argv[i + 1], 10);
        if (!Number.isFinite(parsed) || parsed <= 0) {
          throw new Error(`Invalid --max-packages value: ${argv[i + 1]}`);
        }
        flags.maxPackages = parsed;
        i++;
        break;
      }
      case "--no-fetch":
        flags.noFetch = true;
        break;
      case "--verbose":
        flags.verbose = true;
        break;
      case "--help":
      case "-h":
        flags.help = true;
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return flags;
}

function printHelp() {
  console.log(`Usage: node scripts/pre-validate.mjs [options]

Pre-push validation for Lodestar monorepo.

Options:
  --quick              Fast mode (disables strict build step)
  --strict             Strict mode (default; includes build step)
  --base <ref>         Base ref for merge-base (fallback: @{upstream}, origin/unstable)
  --all                Treat all packages as affected
  --dry-run            Print commands without executing
  --ci-order           Run build before lint/typecheck
  --max-packages <n>   Max targeted packages before global tests fallback (default: ${DEFAULT_MAX_PACKAGES})
  --no-fetch           Skip git fetch step
  --verbose            Verbose logs
  --help, -h           Show this help
`);
}

function runSpawn(cmd, args, options = {}) {
  const {cwd = ROOT_DIR, capture = false, dryRun = false, verbose = false, allowFailure = false} = options;
  const pretty = [cmd, ...args].join(" ");
  if (dryRun) {
    console.log(`${ICON.skip} ${paint("gray", "[dry-run]")} ${pretty}`);
    return Promise.resolve({code: 0, stdout: "", stderr: ""});
  }
  if (verbose) {
    console.log(`${ICON.info} ${paint("gray", pretty)}`);
  }

  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      cwd,
      stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
    });

    let stdout = "";
    let stderr = "";

    if (capture && child.stdout) {
      child.stdout.on("data", (chunk) => {
        stdout += String(chunk);
      });
    }
    if (capture && child.stderr) {
      child.stderr.on("data", (chunk) => {
        stderr += String(chunk);
      });
    }

    child.on("error", (error) => {
      reject(error);
    });

    child.on("close", (code) => {
      if (code === 0 || allowFailure) {
        resolve({code: code ?? 1, stdout, stderr});
        return;
      }

      const msg = stderr.trim() || stdout.trim() || `Command failed (${code}): ${pretty}`;
      reject(new Error(msg));
    });
  });
}

async function step(name, action) {
  const started = Date.now();
  console.log(`${ICON.step} ${paint("blue", name)}`);
  try {
    const result = await action();
    const elapsed = Date.now() - started;
    console.log(`${ICON.ok} ${paint("green", `${name} (${formatMs(elapsed)})`)}`);
    return result;
  } catch (error) {
    const elapsed = Date.now() - started;
    console.error(`${ICON.fail} ${paint("red", `${name} failed (${formatMs(elapsed)})`)}`);
    throw error;
  }
}

function listWorkspacePackages() {
  if (!fs.existsSync(PACKAGES_DIR)) {
    throw new Error(`Missing packages directory: ${PACKAGES_DIR}`);
  }

  /** @type {Map<string, {
   * dir: string;
   * name: string;
   * localName: string;
   * deps: string[];
   * scripts: Record<string, string>;
   * }>}
   */
  const packages = new Map();

  const dirs = fs.readdirSync(PACKAGES_DIR, {withFileTypes: true});
  for (const entry of dirs) {
    if (!entry.isDirectory()) continue;
    const localName = entry.name;
    const dir = path.join(PACKAGES_DIR, localName);
    const pkgPath = path.join(dir, "package.json");
    if (!fs.existsSync(pkgPath)) continue;

    const raw = fs.readFileSync(pkgPath, "utf8");
    const json = JSON.parse(raw);
    if (!json.name || typeof json.name !== "string") {
      throw new Error(`Invalid or missing package name in ${pkgPath}`);
    }

    const depSets = [
      json.dependencies ?? {},
      json.devDependencies ?? {},
      json.peerDependencies ?? {},
      json.optionalDependencies ?? {},
    ];
    const deps = [];
    for (const depSet of depSets) {
      for (const [depName, depVersion] of Object.entries(depSet)) {
        if (typeof depVersion === "string" && depVersion.startsWith("workspace:")) {
          deps.push(depName);
        }
      }
    }

    packages.set(localName, {
      dir,
      name: json.name,
      localName,
      deps,
      scripts: json.scripts ?? {},
    });
  }

  return packages;
}

function buildDependentsGraph(packagesByLocalName) {
  /** @type {Map<string, Set<string>>} */
  const dependentsByPackageName = new Map();

  const packageNames = new Set();
  for (const pkg of packagesByLocalName.values()) {
    packageNames.add(pkg.name);
    if (!dependentsByPackageName.has(pkg.name)) {
      dependentsByPackageName.set(pkg.name, new Set());
    }
  }

  for (const pkg of packagesByLocalName.values()) {
    for (const depName of pkg.deps) {
      if (!packageNames.has(depName)) continue;
      if (!dependentsByPackageName.has(depName)) {
        dependentsByPackageName.set(depName, new Set());
      }
      dependentsByPackageName.get(depName).add(pkg.name);
    }
  }

  return dependentsByPackageName;
}

function transitiveDependents(seedPackageNames, dependentsByPackageName) {
  const queue = [...seedPackageNames];
  const visited = new Set(seedPackageNames);

  while (queue.length > 0) {
    const current = queue.shift();
    const dependents = dependentsByPackageName.get(current);
    if (!dependents) continue;
    for (const dependent of dependents) {
      if (visited.has(dependent)) continue;
      visited.add(dependent);
      queue.push(dependent);
    }
  }

  return visited;
}

async function detectBaseRef(flags) {
  if (flags.base) return flags.base;

  const upstream = await runSpawn("git", ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], {
    capture: true,
    dryRun: flags.dryRun,
    verbose: flags.verbose,
    allowFailure: true,
  });
  if (upstream.code === 0) {
    const ref = upstream.stdout.trim();
    if (ref) return ref;
  }
  return DEFAULT_BASE_FALLBACK;
}

async function getChangedFiles(baseRef, flags) {
  const mergeBaseResult = await runSpawn("git", ["merge-base", baseRef, "HEAD"], {
    capture: true,
    dryRun: flags.dryRun,
    verbose: flags.verbose,
  });
  const mergeBase = mergeBaseResult.stdout.trim();
  if (!mergeBase && !flags.dryRun) {
    throw new Error(`Unable to resolve merge-base for ${baseRef}`);
  }

  const range = flags.dryRun ? `${baseRef}..HEAD` : `${mergeBase}..HEAD`;
  const diffResult = await runSpawn("git", ["diff", "--name-only", "-z", "--diff-filter=ACMRD", range], {
    capture: true,
    dryRun: flags.dryRun,
    verbose: flags.verbose,
  });

  if (flags.dryRun) return [];
  return diffResult.stdout
    .split("\0")
    .filter(Boolean);
}

function classifyChanges(changedFiles, packagesByLocalName) {
  /** @type {Set<string>} */
  const sourceChangedLocals = new Set();
  /** @type {Set<string>} */
  const testChangedLocals = new Set();

  let lintOnly = false;
  let allPackages = false;

  const rootConfigNames = new Set([
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "tsconfig.json",
    "tsconfig.base.json",
    "tsconfig.build.json",
    "vitest.workspace.ts",
    "biome.json",
    "biome.jsonc",
    "lerna.json",
  ]);

  for (const filePath of changedFiles) {
    const normalized = filePath.replace(/\\/g, "/");

    if (normalized.startsWith("packages/")) {
      const parts = normalized.split("/");
      const localName = parts[1];
      const area = parts[2] ?? "";

      if (!packagesByLocalName.has(localName)) {
        continue;
      }

      if (area === "src") {
        sourceChangedLocals.add(localName);
      } else if (area === "test") {
        testChangedLocals.add(localName);
      } else {
        // Non src/test package files can affect package behavior, treat as source change.
        sourceChangedLocals.add(localName);
      }
      continue;
    }

    if (normalized.startsWith("docs/") || normalized.startsWith("scripts/")) {
      lintOnly = true;
      continue;
    }

    const topLevel = normalized.split("/")[0];
    const isTopLevelFile = !normalized.includes("/");
    if (isTopLevelFile && rootConfigNames.has(topLevel)) {
      allPackages = true;
      continue;
    }

    const isLikelyRootConfig =
      isTopLevelFile &&
      (topLevel.endsWith(".config.js") ||
        topLevel.endsWith(".config.cjs") ||
        topLevel.endsWith(".config.mjs") ||
        topLevel.endsWith(".config.ts") ||
        topLevel.startsWith("."));
    if (isLikelyRootConfig) {
      allPackages = true;
    }
  }

  return {sourceChangedLocals, testChangedLocals, lintOnly, allPackages};
}

function packageNamesFromLocals(locals, packagesByLocalName) {
  const out = new Set();
  for (const localName of locals) {
    const pkg = packagesByLocalName.get(localName);
    if (pkg) out.add(pkg.name);
  }
  return out;
}

function selectAffectedPackages(scope, flags, packagesByLocalName, dependentsByPackageName) {
  if (flags.all || scope.allPackages) {
    return new Set([...packagesByLocalName.values()].map((p) => p.name));
  }

  const sourceNames = packageNamesFromLocals(scope.sourceChangedLocals, packagesByLocalName);
  const testNames = packageNamesFromLocals(scope.testChangedLocals, packagesByLocalName);

  // In quick mode, only test directly changed packages (no transitive dependents)
  if (flags.quick) {
    const direct = new Set(sourceNames);
    for (const testName of testNames) {
      direct.add(testName);
    }
    return direct;
  }

  // In strict mode, include transitive dependents of source changes
  const fromSource = transitiveDependents(sourceNames, dependentsByPackageName);
  for (const name of sourceNames) fromSource.add(name);

  for (const testName of testNames) {
    fromSource.add(testName);
  }

  return fromSource;
}

function collectPackageNames(packagesByLocalName) {
  return [...packagesByLocalName.values()].map((pkg) => pkg.name);
}

function pnpmRecursiveArgs(scriptName, packageNames) {
  const args = ["-r"];
  for (const pkgName of packageNames) {
    args.push("--filter", pkgName);
  }
  args.push("run", scriptName);
  return args;
}

async function runValidation(flags) {
  console.log(`${ICON.start} ${paint("bold", "Lodestar pre-push validation")}`);

  const packagesByLocalName = listWorkspacePackages();
  const dependentsByPackageName = buildDependentsGraph(packagesByLocalName);

  const state = {
    baseRef: null,
    changedFiles: [],
    scope: null,
    affectedPackages: new Set(),
    lintOnly: false,
    runGlobalTests: false,
  };

  const steps = flags.ciOrder
    ? ["fetch", "detect", "build", "lintTypecheck", "tests"]
    : ["fetch", "detect", "lintTypecheck", "build", "tests"];

  for (const stepName of steps) {
    if (stepName === "fetch") {
      await step("Fetch", async () => {
        state.baseRef = await detectBaseRef(flags);
        console.log(`${ICON.info} Base ref: ${paint("cyan", state.baseRef)}`);
        if (flags.noFetch) {
          console.log(`${ICON.skip} Skipping fetch (--no-fetch)`);
          return;
        }

        const remote = state.baseRef.includes("/") ? state.baseRef.split("/")[0] : null;
        if (remote && remote !== "@{upstream}") {
          await runSpawn("git", ["fetch", "--quiet", remote], {
            dryRun: flags.dryRun,
            verbose: flags.verbose,
          });
          return;
        }
        await runSpawn("git", ["fetch", "--quiet"], {
          dryRun: flags.dryRun,
          verbose: flags.verbose,
        });
      });
      continue;
    }

    if (stepName === "detect") {
      await step("Detect scope", async () => {
        if (flags.all) {
          state.affectedPackages = new Set(collectPackageNames(packagesByLocalName));
          state.lintOnly = false;
          state.scope = {
            sourceChangedLocals: new Set(),
            testChangedLocals: new Set(),
            lintOnly: false,
            allPackages: true,
          };
          console.log(`${ICON.info} --all enabled; all packages affected.`);
          return;
        }

        state.changedFiles = await getChangedFiles(state.baseRef, flags);
        state.scope = classifyChanges(state.changedFiles, packagesByLocalName);
        state.lintOnly = state.scope.lintOnly && !state.scope.allPackages && state.scope.sourceChangedLocals.size === 0 && state.scope.testChangedLocals.size === 0;
        state.affectedPackages = selectAffectedPackages(state.scope, flags, packagesByLocalName, dependentsByPackageName);

        if (flags.verbose) {
          for (const changed of state.changedFiles) {
            console.log(`${ICON.info} changed: ${paint("gray", changed)}`);
          }
        }

        console.log(`${ICON.info} Changed files: ${state.changedFiles.length}`);
        console.log(`${ICON.info} Affected packages: ${state.affectedPackages.size}`);
        if (state.lintOnly) {
          console.log(`${ICON.info} Lint-only scope detected (docs/scripts changes).`);
        }
        if (state.affectedPackages.size === 0 && !state.lintOnly) {
          console.log(`${ICON.info} No package-impacting changes detected.`);
        }
      });
      continue;
    }

    if (stepName === "lintTypecheck") {
      await step("Lint + Typecheck", async () => {
        if (state.affectedPackages.size === 0 && !state.lintOnly) {
          console.log(`${ICON.skip} Nothing to lint/typecheck.`);
          return;
        }

        // Lint is always global — Lodestar uses `biome check` at root level
        const lintTask = runSpawn("pnpm", ["lint"], {
          dryRun: flags.dryRun,
          verbose: flags.verbose,
        });
        if (state.lintOnly) {
          await lintTask;
          return;
        }
        const typeTask = runSpawn("pnpm", ["check-types"], {
          dryRun: flags.dryRun,
          verbose: flags.verbose,
        });
        await Promise.all([lintTask, typeTask]);
      });
      continue;
    }

    if (stepName === "build") {
      await step("Build", async () => {
        if (!flags.strict) {
          console.log(`${ICON.skip} Build disabled in --quick mode.`);
          return;
        }
        if (state.lintOnly) {
          console.log(`${ICON.skip} Build skipped for lint-only scope.`);
          return;
        }
        if (state.affectedPackages.size === 0) {
          console.log(`${ICON.skip} Nothing to build.`);
          return;
        }
        // Build all — pnpm -r build handles dependency order automatically
        await runSpawn("pnpm", ["build"], {
          dryRun: flags.dryRun,
          verbose: flags.verbose,
        });
      });
      continue;
    }

    if (stepName === "tests") {
      await step("Unit tests", async () => {
        if (state.lintOnly) {
          console.log(`${ICON.skip} Unit tests skipped for lint-only scope.`);
          return;
        }
        if (state.affectedPackages.size === 0) {
          console.log(`${ICON.skip} No affected packages to test.`);
          return;
        }

        const pkgs = [...state.affectedPackages].sort();
        state.runGlobalTests = pkgs.length > flags.maxPackages;

        if (state.runGlobalTests) {
          console.log(
            `${ICON.warn} Affected packages (${pkgs.length}) exceed --max-packages (${flags.maxPackages}); running global tests.`,
          );
          await runSpawn("pnpm", ["test:unit"], {
            dryRun: flags.dryRun,
            verbose: flags.verbose,
          });
          return;
        }

        const byName = new Map([...packagesByLocalName.values()].map((pkg) => [pkg.name, pkg]));
        const testable = [];
        for (const pkgName of pkgs) {
          const pkg = byName.get(pkgName);
          if (!pkg) continue;
          if (!Object.hasOwn(pkg.scripts, "test:unit")) {
            console.log(`${ICON.warn} ${pkgName} has no test:unit script; skipping.`);
            continue;
          }
          testable.push(pkgName);
        }

        if (testable.length === 0) {
          console.log(`${ICON.skip} No packages with test:unit script in affected scope.`);
          return;
        }

        await runSpawn("pnpm", pnpmRecursiveArgs("test:unit", testable), {
          dryRun: flags.dryRun,
          verbose: flags.verbose,
        });
      });
      continue;
    }
  }
}

async function main() {
  const started = Date.now();
  try {
    const flags = parseArgs(process.argv.slice(2));
    if (flags.help) {
      printHelp();
      return;
    }
    await runValidation(flags);
    const elapsed = Date.now() - started;
    console.log(`${ICON.time} ${paint("green", `All validation steps passed in ${formatMs(elapsed)}`)}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`${ICON.fail} ${paint("red", message)}`);
    process.exitCode = 1;
  }
}

await main();
