#!/usr/bin/env python3
"""Compile a shard's TEST-AUDIT-BRIEF.md. Invoked by /manager-mode Phase 3.4.1.

Why this exists
---------------
3.4.1 is a *compilation* step, not a judgment step: the auditor needs the full
umbrella test, the full shard tests, the shard's BOUNDARIES.md, the contract
symbols its briefs import, and the spec lines its briefs cite — verbatim and
unfiltered. Done by hand, the overlord has to READ every one of those files
(input tokens) and then WRITE them back out through the Write tool (output
tokens, at the overlord's tier), after which the whole package sits in the
overlord's prefix for every remaining turn of the cascade. That is the single
most expensive way to move bytes from one file to another.

This script moves them for free. It reads exactly what 3.4.1 lists and writes
the brief to disk; the overlord never has to hold the content at all — it adds
only the two bullets that need its own cross-shard knowledge (sibling-shard
awareness, already-litigated decisions).

Deliberately NOT a judgment step: nothing here filters, ranks, or summarises
what the auditor sees. Umbrella, tests and BOUNDARIES.md go in whole. The only
two narrowed sections are the ones 3.4.1 itself scopes — the contract excerpt
(only symbols the briefs' `contract_imports` name) and the spec excerpt (only
the `spec_lines` ranges the briefs cite) — so the package stays bounded without
the auditor losing anything a brief actually points at.

Exit codes: 0 brief written complete, 1 brief written but a section had a gap
(missing umbrella/test/BOUNDARIES file, unresolvable contract symbol or spec
range) or no briefs matched, 2 resolution/config error. A gap is a real finding
— it means the auditor would be judging without something 3.4.1 requires — so
it exits non-zero and names each gap on stderr rather than writing a quietly
incomplete package.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_invariants as ci  # noqa: E402
import run_gates as rg  # noqa: E402


# ---------- input resolution ----------

def shard_briefs(briefs_dir: Path, wave: int | None,
                 shard: str | None) -> list[ci.Brief]:
    """Every brief in this (wave, shard) group, leaf-id order.

    Shard resolution mirrors `check_invariants._shard`: explicit frontmatter
    first, then a `shard-<id>/` parent directory. `shard=None` means "whatever
    the wave holds", which is the right answer for the unsharded single-shard
    wave that writes to `audits/wave-N/default/`.
    """
    out: list[ci.Brief] = []
    for path in sorted(briefs_dir.rglob("leaf-*.md")):
        brief = ci.parse_brief(path)
        if brief is None:
            continue
        if wave is not None and ci._wave(brief) != wave:
            continue
        if shard is not None and ci._shard(brief) != shard:
            continue
        out.append(brief)
    return sorted(out, key=lambda b: b.leaf_id)


UMBRELLA_TOKEN_RE = re.compile(r"[\w./-]+")


def umbrella_files(root: Path, umbrella_cmd: str) -> list[Path]:
    """Test files named by `umbrella_test_cmd`.

    The command is a shell line (`uv run pytest tests/umbrella_cache.py -q`),
    so take every token that resolves to a real file under the root. A command
    that names a directory or nothing at all yields an empty list, and the
    caller reports that rather than writing a brief with a silent hole where
    the umbrella should be.
    """
    found: list[Path] = []
    for token in UMBRELLA_TOKEN_RE.findall(umbrella_cmd or ""):
        candidate = root / token
        if candidate.is_file():
            found.append(candidate)
    return list(dict.fromkeys(found))


def spec_ranges(briefs: list[ci.Brief]) -> dict[str, list[tuple[int, int]]]:
    """`spec_file` -> merged, sorted `spec_lines` ranges the briefs cite."""
    raw: dict[str, list[tuple[int, int]]] = {}
    for b in briefs:
        spec_file = b.frontmatter.get("spec_file")
        lines = b.frontmatter.get("spec_lines")
        if not isinstance(spec_file, str) or not spec_file:
            continue
        m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(lines))
        if not m:
            continue
        start, end = int(m.group(1)), int(m.group(2))
        if end < start:
            start, end = end, start
        raw.setdefault(spec_file, []).append((start, end))
    merged: dict[str, list[tuple[int, int]]] = {}
    for spec_file, ranges in raw.items():
        ordered = sorted(ranges)
        acc: list[tuple[int, int]] = []
        for start, end in ordered:
            if acc and start <= acc[-1][1] + 1:
                acc[-1] = (acc[-1][0], max(acc[-1][1], end))
            else:
                acc.append((start, end))
        merged[spec_file] = acc
    return merged


SCALE_HEADING_RE = re.compile(r"^(#{1,6})\s*scale\s*&?\s*(and\s+)?boundary\s+profile\b",
                              re.IGNORECASE)


def scale_profile(spec_text: str) -> str | None:
    """The spec's `Scale & Boundary Profile` section, verbatim, or None.

    3.4.2's BOUNDARY & SCALE FIDELITY check reads BOUNDARIES.md *against* the
    profile the spec pinned, so the profile has to travel with the package even
    when it falls outside the `spec_lines` ranges the briefs cite (it usually
    does — it is a spec-wide section, not a per-leaf AC).
    """
    lines = spec_text.splitlines()
    start = next((i for i, ln in enumerate(lines) if SCALE_HEADING_RE.match(ln)), None)
    if start is None:
        return None
    depth = len(SCALE_HEADING_RE.match(lines[start]).group(1))
    end = start + 1
    while end < len(lines):
        m = re.match(r"^(#{1,6})\s", lines[end])
        if m and len(m.group(1)) <= depth:
            break
        end += 1
    return "\n".join(lines[start:end]).rstrip()


def contract_symbols(briefs: list[ci.Brief]) -> list[str]:
    """Every symbol the shard's briefs import, deduped, order preserved."""
    out: list[str] = []
    for b in briefs:
        imports = b.frontmatter.get("contract_imports") or []
        if isinstance(imports, str):
            imports = [imports]
        for sym in imports:
            if isinstance(sym, str) and sym.strip():
                out.append(sym.strip())
    return list(dict.fromkeys(out))


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def symbol_block(text: str, symbol: str) -> str | None:
    """The definition block for `symbol` in a contract file, or None.

    Takes the last dotted component (`src.types.Job` -> `Job`), finds the
    line that defines it, and returns from that line (plus any decorators
    immediately above it) to the next line at or below its own indentation.
    Works for Python `class`/`def`/constant assignments and TS
    `export`ed declarations; anything it cannot locate is reported as a
    missing symbol rather than silently dropped, because a contract symbol a
    brief imports and the auditor cannot see is exactly the gap 3.4.1's
    contract excerpt exists to close.
    """
    name = symbol.split(".")[-1].strip()
    if not name:
        return None
    lines = text.splitlines()
    pattern = re.compile(
        r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?"
        r"(?:class|def|interface|type|enum|function|const|let|var)\s+"
        + re.escape(name) + r"\b"
        r"|^\s*" + re.escape(name) + r"\s*[:=]"
    )
    start = next((i for i, line in enumerate(lines) if pattern.match(line)), None)
    if start is None:
        return None
    base = _indent(lines[start])
    while start > 0 and lines[start - 1].lstrip().startswith("@"):
        start -= 1
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and _indent(line) <= base:
            break
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


# ---------- rendering ----------

def fence_for(path: Path) -> str:
    return {
        ".py": "python", ".ts": "ts", ".tsx": "tsx", ".js": "js",
        ".sql": "sql", ".md": "markdown", ".toml": "toml",
    }.get(path.suffix, "")


def read_block(root: Path, path: Path, heading: str) -> str:
    rel = path.relative_to(root) if path.is_relative_to(root) else path
    return (f"### {heading}\n\n`{rel}`\n\n"
            f"```{fence_for(path)}\n{path.read_text().rstrip()}\n```\n")


def render(root: Path, cfg: dict[str, Any], slug: str, wave: int,
           shard_label: str, briefs: list[ci.Brief],
           umbrella: list[Path], boundaries: Path | None) -> tuple[str, list[str]]:
    """The brief text plus the list of gaps worth telling the overlord about."""
    gaps: list[str] = []
    parts: list[str] = [
        f"# TEST-AUDIT-BRIEF — {slug}, wave {wave}, shard {shard_label}",
        "",
        "Compiled by `build_audit_brief.py` (Phase 3.4.1). Everything below is",
        "verbatim from the files named; nothing was filtered or summarised.",
        "The contract and spec sections are narrowed to exactly what this",
        "shard's briefs cite — `contract_imports` and `spec_lines` — per 3.4.1.",
        "",
        "## 1. Umbrella test (full text)",
        "",
    ]
    if umbrella:
        for path in umbrella:
            parts.append(read_block(root, path, "Umbrella"))
    else:
        gaps.append("umbrella: `umbrella_test_cmd` named no readable test file")
        parts.append("_No umbrella test file resolved from "
                     f"`umbrella_test_cmd` (`{cfg.get('umbrella_test_cmd', '')}`). "
                     "The overlord must paste it in by hand._\n")

    parts += ["## 2. The shard's stated goal", "",
              "| leaf | spec_lines | contract_imports | test files | impl files |",
              "|------|-----------|------------------|------------|------------|"]
    for b in briefs:
        parts.append(
            f"| {b.leaf_id} | {b.frontmatter.get('spec_file', '?')}:"
            f"{b.frontmatter.get('spec_lines', '?')} | "
            + ", ".join(f"`{s}`" for s in (b.frontmatter.get('contract_imports') or []))
            + " | " + ", ".join(f"`{p}`" for p in ci._leaf_paths(b, "test"))
            + " | " + ", ".join(f"`{p}`" for p in ci._leaf_paths(b, "impl")) + " |")
    parts.append("")

    parts += ["## 3. Spec excerpt (only the ACs these briefs cite)", ""]
    ranges = spec_ranges(briefs)
    if not ranges:
        gaps.append("spec: no brief carries a parseable `spec_file` + `spec_lines`")
        parts.append("_No `spec_lines` range resolved from this shard's briefs._\n")
    for spec_file, spans in sorted(ranges.items()):
        spec_path = root / spec_file
        if not spec_path.is_file():
            gaps.append(f"spec: `{spec_file}` not found on disk")
            parts.append(f"_`{spec_file}` not found on disk._\n")
            continue
        spec_text = spec_path.read_text()
        spec_lines = spec_text.splitlines()
        for start, end in spans:
            body = "\n".join(spec_lines[start - 1:end])
            parts.append(f"`{spec_file}` lines {start}-{end}:\n\n"
                         f"```markdown\n{body.rstrip()}\n```\n")
        profile = scale_profile(spec_text)
        if profile:
            parts.append(f"`{spec_file}` — Scale & Boundary Profile "
                         "(spec-wide, quoted whole because 3.4.2 grades "
                         "BOUNDARIES.md against it):\n\n"
                         f"```markdown\n{profile}\n```\n")
        else:
            gaps.append(f"spec: no `Scale & Boundary Profile` section in `{spec_file}`")

    parts += ["## 4. Contract excerpt (only symbols in `contract_imports`)", ""]
    contract_rel = str(cfg.get("type_contract_path") or "")
    symbols = contract_symbols(briefs)
    contract_path = (root / contract_rel) if contract_rel else None
    if not symbols:
        parts.append("_This shard's briefs import no contract symbols._\n")
    elif contract_path is None or not contract_path.is_file():
        gaps.append(f"contract: `{contract_rel or '<unset type_contract_path>'}` "
                    "not found on disk")
        parts.append(f"_Contract file `{contract_rel}` not found on disk; "
                     f"symbols cited: {', '.join(symbols)}._\n")
    else:
        contract_text = contract_path.read_text()
        fence = fence_for(contract_path)
        missing: list[str] = []
        for sym in symbols:
            block = symbol_block(contract_text, sym)
            if block is None:
                missing.append(sym)
                continue
            parts.append(f"`{contract_rel}` — `{sym}`:\n\n"
                         f"```{fence}\n{block.rstrip()}\n```\n")
        if missing:
            gaps.append("contract: symbols not found in "
                        f"`{contract_rel}`: {', '.join(missing)}")
            parts.append("_Symbols cited by a brief but not locatable in the "
                         f"contract: {', '.join(missing)}._\n")

    parts += ["## 5. Tests under audit (full text)", ""]
    test_paths: list[Path] = []
    for b in briefs:
        for rel in ci._leaf_paths(b, "test"):
            test_paths.append(root / rel)
    seen: set[Path] = set()
    wrote_any = False
    for path in test_paths:
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            gaps.append(f"tests: declared test file `{path}` not on disk")
            parts.append(f"_Declared test file `{path}` not found on disk._\n")
            continue
        parts.append(read_block(root, path, path.name))
        wrote_any = True
    if not wrote_any and not test_paths:
        gaps.append("tests: this shard's briefs declare no test files")
        parts.append("_This shard's briefs declare no test files._\n")

    parts += ["## 6. BOUNDARIES.md (full text)", ""]
    if boundaries is not None and boundaries.is_file():
        parts.append(read_block(root, boundaries, "BOUNDARIES.md"))
    else:
        gaps.append("boundaries: BOUNDARIES.md missing for this shard")
        parts.append("_No `BOUNDARIES.md` for this shard. The 2.6 boundary "
                     "sweep either has not run or wrote elsewhere._\n")

    parts += [
        "## 7. Sibling-shard awareness",
        "",
        "_Overlord fills in by hand: if a sibling shard's brief set shares a "
        "contract symbol or an adjacent AC, name the shard and quote only the "
        "overlapping symbol/AC. Write `none` if there is no sibling shard._",
        "",
        "## 8. Already litigated",
        "",
        "_Overlord fills in by hand: wave-sweep dismissals or yellow-flags "
        "touching this shard's territory, so the auditor does not re-open a "
        "decision the user already made. Write `none` if there are none._",
        "",
    ]
    return "\n".join(parts), gaps


# ---------- cli ----------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="compile a shard's TEST-AUDIT-BRIEF.md (/manager-mode 3.4.1)")
    p.add_argument("--cascade", "--slug", dest="cascade",
                   help="cascade slug; auto-detected when exactly one exists")
    p.add_argument("--wave", type=int, default=1, help="wave number (default 1)")
    p.add_argument("--shard", default="",
                   help="shard id (e.g. shard-A). Omit for an unsharded wave, "
                        "which writes to audits/wave-<wave>/default/")
    p.add_argument("--briefs-dir", type=Path,
                   help="path to briefs dir; default from .claude-swarm.toml")
    p.add_argument("--root", type=Path, default=Path.cwd(),
                   help="project root (walks up looking for .claude-swarm.toml)")
    p.add_argument("--out", type=Path,
                   help="output path; default "
                        "<cascade>/audits/wave-<wave>/<shard-or-default>/"
                        "TEST-AUDIT-BRIEF.md")
    args = p.parse_args(argv)

    root = ci.git_root(args.root)
    cfg = ci.load_config(root)
    slug = ci.discover_cascade_slug(root, args.cascade)
    briefs_dir = ci.resolve_briefs_dir(root, cfg, args.briefs_dir, args.cascade)
    if not briefs_dir.exists():
        print(f"briefs_dir not found: {briefs_dir}", file=sys.stderr)
        found = ci.cascade_candidates(root)
        if len(found) > 1 and not args.cascade:
            print(f"multiple cascades present ({', '.join(found)}); "
                  f"pass --cascade <slug>", file=sys.stderr)
        return 2

    shard = args.shard or ""
    briefs = shard_briefs(briefs_dir, args.wave, shard if shard else None)
    if not briefs and shard:
        # An unsharded wave written to `default/` has shard "" on every brief;
        # asking for `--shard default` must not silently produce an empty brief.
        briefs = shard_briefs(briefs_dir, args.wave, None) if shard == "default" else []
    if not briefs:
        print(f"no briefs for wave {args.wave}"
              + (f", shard {shard}" if shard else "")
              + f" under {briefs_dir}", file=sys.stderr)
        return 1

    shard_label = shard or "default"
    out_dir = rg.audit_dir(root, slug, args.wave, "" if shard_label == "default" else shard)
    out = args.out or (out_dir / "TEST-AUDIT-BRIEF.md")
    boundaries = out_dir / "BOUNDARIES.md"
    umbrella = umbrella_files(root, str(cfg.get("umbrella_test_cmd") or ""))

    text, gaps = render(root, cfg, slug or "<cascade>", args.wave, shard_label,
                        briefs, umbrella, boundaries)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)

    n_tests = sum(len(ci._leaf_paths(b, "test")) for b in briefs)
    print(f"TEST-AUDIT-BRIEF written to {out}")
    print(f"--- {len(briefs)} briefs, {n_tests} test files, "
          f"{len(umbrella)} umbrella file(s), "
          f"{len(contract_symbols(briefs))} contract symbols, "
          f"{len(text.splitlines())} lines, {len(gaps)} gaps ---")
    for gap in gaps:
        print(f"GAP: {gap}", file=sys.stderr)
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
