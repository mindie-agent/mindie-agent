"""Read-only consumer facade over the frozen MaterialStore API.

The pilot deliberately uses library query/read, not native MCP installation.
Collection, summary generation, feedback and publication are absent.
"""
import json
from pathlib import Path
import sys
import time

from mindie_knowledge.materials import MaterialStore
from mindie_knowledge.materials.references import parse_read_ref


def main():
    root, operation, argument = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    started = time.monotonic()
    store = MaterialStore(root / "store", "pilot")
    try:
        if operation == "query":
            value = {"results": store.search(argument, limit=5),
                     "note": "Fallible historical reference; verify applicability against current task files."}
        elif operation == "read":
            parsed = parse_read_ref(argument, domain="pilot")
            task_id = parsed["task_id"]
            revision = store.current_revisions(task_id)["draft"]
            value = store.read_current(task_id, source="draft", revision=revision,
                                       block_id=parsed.get("block_id"), sha256=parsed.get("sha256"))
        else:
            raise ValueError("use query TEXT or read REF")
        output = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with (root / "reads.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"operation": operation, "argument": argument,
                                     "bytes": len(output.encode()),
                                     "elapsed_seconds": time.monotonic() - started}) + "\n")
        print(output)
    finally:
        store.close()


if __name__ == "__main__":
    main()
