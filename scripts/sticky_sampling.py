#!/usr/bin/env python3
"""
sticky_sampling.py — Phase C: associative priming + DMN roaming

Runs at the end of Heartbeat Step 4 (before Step 5).
Input:  state/world_context.json + state/active_loops.md
Output: state/primed_sticky.md (one loop context, or empty)

Logic:
  1. Set A (priming): BGE semantic match between world_context.scene
     and ALL active loop tags → loops that exceed threshold
  2. Set B (DMN roaming): if A is empty, randomly sample one sticky loop
  3. Priming takes priority; if A is non-empty, randomly pick from A
     (no score-based ranking)
"""

import sys
from pathlib import Path

import json
import re
import random

# ── Paths ─────────────────────────────────────────────
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
WORLD_CTX = WORKSPACE_DIR / "state" / "world_context.json"
ACTIVE_LOOPS = WORKSPACE_DIR / "state" / "active_loops.md"
PRIMED_STICKY = WORKSPACE_DIR / "state" / "primed_sticky.md"

# BGE matching threshold — scene vs tags phase_c_score must exceed this
# ⚠️ This value (0.48) was calibrated on Chinese tags + 7 days of one user's data.
# English embeddings + your tag vocabulary + your scene phrasing produce different
# similarity distributions. Run for a week, log scores, then tune.
PRIMING_THRESHOLD = 0.48


# ── Parse active_loops.md ─────────────────────────────
def parse_active_loops(content: str) -> list[dict]:
    """Parse active_loops.md into a list of loop dicts."""
    loops = []
    current_id = None

    for line in content.split("\n"):
        # Title line: - **loop_id** | weight: N | ...
        m = re.match(r"^- \*\*(.+?)\*\* \| (.+)", line)
        if m:
            current_id = m.group(1).strip()
            fields_str = m.group(2)
            fields = {"id": current_id}

            for part in fields_str.split("|"):
                part = part.strip()
                kv = part.split(":", 1)
                if len(kv) == 2:
                    fields[kv[0].strip()] = kv[1].strip()

            fields["sticky"] = fields.get("sticky", "").lower() == "true"
            try:
                fields["weight"] = int(fields.get("weight", "0"))
            except ValueError:
                fields["weight"] = 0
            try:
                fields["suppressed"] = int(fields.get("suppressed", "0"))
            except ValueError:
                fields["suppressed"] = 0

            tags_str = fields.get("tags", "")
            if tags_str:
                fields["tags"] = [t.strip() for t in tags_str.strip("[]").split(",") if t.strip()]
            else:
                fields["tags"] = []

            loops.append(fields)
            continue

        # Tags line: tags: [tag1, tag2, ...]
        if loops:
            tag_match = re.match(r"^\s*tags[:：]\s*\[(.+?)\]", line)
            if tag_match:
                loops[-1]["tags"] = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
                continue

        # Content line: Content: xxx
        if loops:
            content_match = re.match(r"^\s*(?:content)[:：]\s*(.+)", line, re.IGNORECASE)
            if content_match:
                loops[-1]["content"] = content_match.group(1).strip()
                continue

    return loops


def get_loops_with_tags(loops: list[dict]) -> list[dict]:
    """Return all active loops that have tags (for priming, set A)."""
    return [l for l in loops if l.get("tags")]


def get_sticky_loops_with_tags(loops: list[dict]) -> list[dict]:
    """Return sticky loops that have tags (for DMN roaming, set B)."""
    return [l for l in loops if l.get("sticky") and l.get("tags")]


# ── BGE semantic matching ────────────────────────────
def compute_phase_c_score(model, scene: str, tags: list[str]) -> float:
    """
    Phase C matching formula:
    score = 0.7 * sim(scene, tags_combined_mean) + 0.3 * max(sim(scene, each_tag))
    """
    import numpy as np

    scene_vec = model.encode([scene])[0]
    tag_vecs = model.encode(tags)

    combined = np.mean(tag_vecs, axis=0)
    combined = combined / np.linalg.norm(combined)

    scene_norm = scene_vec / np.linalg.norm(scene_vec)
    score_combined = float(np.dot(scene_norm, combined))

    scores_each = []
    for tv in tag_vecs:
        tv_norm = tv / np.linalg.norm(tv)
        scores_each.append(float(np.dot(scene_norm, tv_norm)))
    score_max = max(scores_each)

    return 0.7 * score_combined + 0.3 * score_max


def load_model():
    """Load BGE model with offline enforcement."""
    import os
    # Clear proxy env vars — system SOCKS proxy causes httpx to crash without socksio
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy", "http_proxy", "https_proxy"]:
        os.environ.pop(k, None)
    # Force offline — model is cached; avoids HuggingFace Hub connection timeout
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("BAAI/bge-small-en-v1.5")


# ── Output ───────────────────────────────────────────
def write_primed_sticky(loop: dict | None):
    """Write primed_sticky.md. loop=None writes empty file."""
    if loop is None:
        PRIMED_STICKY.write_text("")
        return

    lines = [
        "# Primed Sticky Loop",
        "",
        f"- **{loop['id']}** | weight: {loop['weight']} | suppressed: {loop['suppressed']}",
        f"  Content: {loop.get('content', '')}",
    ]
    if loop.get("tags"):
        lines.append(f"  tags: [{', '.join(loop['tags'])}]")
    lines.append("")

    PRIMED_STICKY.write_text("\n".join(lines))


# ── Main ─────────────────────────────────────────────
def main():
    # 1. Read world_context
    if not WORLD_CTX.exists():
        print("sticky_sampling: world_context.json not found, skipping", file=sys.stderr)
        write_primed_sticky(None)
        return

    with open(WORLD_CTX) as f:
        ctx = json.load(f)
    scene = ctx.get("scene", "")
    if not scene:
        print("sticky_sampling: scene is empty, skipping", file=sys.stderr)
        write_primed_sticky(None)
        return

    # 2. Read active_loops
    if not ACTIVE_LOOPS.exists():
        print("sticky_sampling: active_loops.md not found, skipping", file=sys.stderr)
        write_primed_sticky(None)
        return

    content = ACTIVE_LOOPS.read_text()
    loops = parse_active_loops(content)
    all_tagged = get_loops_with_tags(loops)
    sticky_tagged = get_sticky_loops_with_tags(loops)

    if not all_tagged:
        print("sticky_sampling: no loops with tags, skipping", file=sys.stderr)
        write_primed_sticky(None)
        return

    # 3. BGE semantic matching — Set A (priming, all loops)
    model = load_model()

    set_a = []
    for loop in all_tagged:
        score = compute_phase_c_score(model, scene, loop["tags"])
        print(f"  {loop['id']}: score={score:.4f}", file=sys.stderr)
        if score >= PRIMING_THRESHOLD:
            set_a.append((loop, score))

    # 4. Sampling
    if set_a:
        chosen = random.choice(set_a)[0]
        print(f"sticky_sampling: priming hit, chose {chosen['id']} from {len(set_a)} candidates", file=sys.stderr)
    else:
        if sticky_tagged:
            chosen = random.choice(sticky_tagged)
            print(f"sticky_sampling: no priming, DMN roaming chose {chosen['id']}", file=sys.stderr)
        else:
            print("sticky_sampling: no priming and no sticky loops, skipping", file=sys.stderr)
            write_primed_sticky(None)
            return

    # 5. Write output
    write_primed_sticky(chosen)
    print(f"sticky_sampling: wrote primed_sticky.md for {chosen['id']}", file=sys.stderr)


if __name__ == "__main__":
    main()
