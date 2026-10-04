"""Run the preregistered twelve-run synthetic pilot with native usage records.

Only disposable fixtures are writable. The selected experiment budgets are
not product defaults. Known harness/auth failures stop remaining trials.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import signal
import subprocess
import sys
import time

from mindie_knowledge.materials import MaterialStore

HERE = Path(__file__).resolve().parent
OUTPUT = Path(sys.argv[1]).resolve()
SOURCE = Path(sys.argv[2]).resolve()
MODEL = "gpt-6-astra"
EFFORT = "low"
SEED = 20261005
INPUT_BUDGET = int(os.environ.get("MINDIE_PILOT_INPUT_BUDGET", "240000"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(case, arm, identifier):
    base = OUTPUT / identifier
    work = base / "work"
    work.mkdir(parents=True)
    for name, body in case["files"].items():
        (work / name).write_text(body, encoding="utf-8")
    started = time.monotonic()
    store = MaterialStore(base / "store", "pilot")
    try:
        for index, material in enumerate(case["materials"] if arm == "reuse" else []):
            task_id = digest(case["id"] + str(index))
            block_id = digest(task_id + ":block")
            task = store.append_batch(task_id, [{"block_id": block_id,
                "text": material["body"], "source_range": {"fixture": index},
                "title": material["title"], "summary": "Historical reference; applicability must be checked."}],
                "Complete source block available via its read reference.", title=material["title"],
                conditions=material["conditions"])
            store.retain_current(task_id, {"draft": task["entry"]["revision"]})
        store.search("initialization")
    finally:
        store.close()
    ingestion = time.monotonic() - started
    reference = [sys.executable, str(HERE / "consumer_reference.py"), str(base)]
    command = "PYTHONPATH=" + shlex.quote(str(SOURCE)) + " " + shlex.join(reference)
    prompt = case["prompt"] + "\n\n" + (
        "Work only in the current directory. Do not inspect other workspaces, test harnesses, "
        "grader files or private data. No network or dependency changes are needed. "
        "If useful, historical reference lookup is available through this command: " + command +
        " query 'search terms'. Read a returned full reference with the same command and "
        "read 'mindie://...'. Use only that interface to access reference material; "
        "do not open its internal files. References may be outdated or wrong; current task files "
        "and actual checks determine applicability. Complete the task within eight tool calls "
        "and keep the final response below 300 words. Do not ask for activation or feedback."
    )
    (base / "prompt.txt").write_text(prompt, encoding="utf-8")
    return {"id": identifier, "case": case["id"], "arm": arm, "base": str(base),
            "ingestion_seconds": ingestion, "prompt_sha256": digest(prompt)}


def run(row):
    base = Path(row["base"])
    command = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
               "--dangerously-bypass-approvals-and-sandbox", "--json", "--color", "never",
               "-m", MODEL, "-c", 'model_reasoning_effort="' + EFFORT + '"',
               "-C", str(base / "work"), "-o", str(base / "response.txt"), "-"]
    started = time.monotonic()
    with (base / "events.jsonl").open("w") as output, (base / "stderr.txt").open("w") as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output, stderr=errors,
                                   text=True, start_new_session=True)
        try:
            process.communicate((base / "prompt.txt").read_text(), timeout=300)
            status = "completed" if process.returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            status = "censored_time_budget"
    events = []
    for line in (base / "events.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    usage = next((e.get("usage") for e in reversed(events) if e.get("type") == "turn.completed"), None)
    completed = [e["item"] for e in events if e.get("type") == "item.completed"]
    calls = [item for item in completed if item.get("type") in {"command_execution", "mcp_tool_call", "web_search", "file_change"}]
    check = subprocess.run([sys.executable, str(HERE / "grade_consumer.py"), "--case", row["case"],
                            "--workspace", str(base / "work")], text=True, capture_output=True, timeout=30)
    (base / "oracle.stdout.txt").write_text(check.stdout)
    (base / "oracle.stderr.txt").write_text(check.stderr)
    reads = [json.loads(line) for line in (base / "reads.jsonl").read_text().splitlines()] if (base / "reads.jsonl").exists() else []
    result = {**row, "status": status, "exit_code": process.returncode,
              "elapsed_seconds": time.monotonic() - started, "usage": usage,
              "reasoning_tokens": (usage or {}).get("reasoning_output_tokens"), "tool_calls": len(calls), "reference_reads": reads,
              "oracle_exit_code": check.returncode,
              "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((base / "work").iterdir()) if p.is_file()}}
    save(base / "result.json", result)
    return result


def main():
    resuming = len(sys.argv) > 3 and sys.argv[3] == "--resume"
    if resuming:
        plan = json.loads((OUTPUT / "plan.json").read_text())
        results = json.loads((OUTPUT / "results.json").read_text())
        plan.setdefault("amendments", []).append({"completed_runs": len(results),
            "input_budget": INPUT_BUDGET,
            "reason": "Native cumulative input includes repeated cached context and exceeded the initial estimate. Preserve all four completed trials and original stop receipt; continue only previously unrun trials under an explicit larger accounting budget."})
        save(OUTPUT / "plan.json", plan)
        done = {r["id"] for r in results}
        rows = [r for r in plan["runs"] if r["id"] not in done]
    else:
        OUTPUT.mkdir(parents=True, exist_ok=False)
        cases = json.loads((HERE / "consumer-cases.json").read_text())["cases"]
        rng = random.Random(SEED)
        rows = []
        for case in cases:
            arms = ["baseline", "reuse"]
            rng.shuffle(arms)
            for arm in arms:
                rows.append(prepare(case, arm, "run-" + digest(str(rng.random()))[:12]))
        save(OUTPUT / "plan.json", {"schema": "consumer-pilot/1", "seed": SEED,
             "model_requested": MODEL, "effort": EFFORT, "model_backend_revision": None,
             "cli": subprocess.check_output(["codex", "--version"], text=True).strip(),
             "source_revision": subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip(),
             "protocol": "native Codex exec consumer plus MaterialStore library query/read; no native MindIE MCP",
             "budgets": {"runs": 12, "parallel": 2, "per_run_seconds": 300,
                         "per_run_tools": 8, "input_tokens": INPUT_BUDGET, "output_tokens": 24000},
             "runs": rows})
        results = []
    # Two independent pairs at a time; each pair's randomized first arm runs
    # before its second arm. Do not transfer histories or model state.
    with ThreadPoolExecutor(max_workers=2) as executor:
        for offset in range(0, len(rows), 4):
            group = rows[offset:offset + 4]
            for indices in ([0, 2], [1, 3]):
                futures = [executor.submit(run, group[i]) for i in indices if i < len(group)]
                batch = [future.result() for future in futures]
                results.extend(batch)
                save(OUTPUT / "results.json", results)
                print(json.dumps([{k: r[k] for k in ("id", "status", "elapsed_seconds", "tool_calls", "usage", "oracle_exit_code")} for r in batch]), flush=True)
                tokens_in = sum((r.get("usage") or {}).get("input_tokens", 0) for r in results)
                tokens_out = sum((r.get("usage") or {}).get("output_tokens", 0) for r in results)
                if any(r["status"] == "failed" and r["usage"] is None for r in batch) or tokens_in >= INPUT_BUDGET or tokens_out >= 24000:
                    save(OUTPUT / "stop.json", {"reason": "known_harness_failure_or_budget", "completed_runs": len(results), "input_tokens": tokens_in, "output_tokens": tokens_out})
                    return


if __name__ == "__main__":
    main()
