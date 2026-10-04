"""Synthetic LangMem interface probe. No provider client, network call or database."""
from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
import json
import platform
import resource
import sys
import time
from pathlib import Path

started = time.perf_counter()
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langmem.short_term import RunningSummary, summarize_messages

import_seconds = time.perf_counter() - started


def units(messages):
    # Deliberately deterministic character units, not a tokenizer or cost estimate.
    return sum(len(str(message.content)) for message in messages)


class FakeHarness:
    def __init__(self, output="FAKE_SUMMARY_V1", fail=False):
        self.output = output
        self.fail = fail
        self.calls = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        if self.fail:
            raise RuntimeError("SYNTHETIC_PROVIDER_FAILURE")
        return AIMessage(content=self.output)


def make_messages(prefix, count, size=80):
    return [
        HumanMessage(id=f"{prefix}-{i}", content=f"SYNTHETIC_{prefix}_{i}:".ljust(size, "x"))
        for i in range(count)
    ]


def run(messages, model, prior=None, **kwargs):
    options = dict(max_tokens=512, max_tokens_before_summary=120,
                   max_summary_tokens=64, token_counter=units)
    options.update(kwargs)
    return summarize_messages(messages, running_summary=prior, model=model, **options)


def ids(messages):
    return [message.id for message in messages if message.id]


small_model = FakeHarness()
small = run(make_messages("small", 1, 16), small_model)
assert len(small_model.calls) == 0 and small.running_summary is None

model = FakeHarness()
batch_one = make_messages("first", 2)
first = run(batch_one, model)
assert len(model.calls) == 1
assert set(ids(model.calls[0])) == {"first-0", "first-1"}
assert first.running_summary is not None

# Persistable plain state; this probe serializes it in memory and rehydrates it.
state = json.loads(json.dumps({
    "summary": first.running_summary.summary,
    "summarized_message_ids": sorted(first.running_summary.summarized_message_ids),
    "last_summarized_message_id": first.running_summary.last_summarized_message_id,
}))
rehydrated = RunningSummary(summary=state["summary"],
    summarized_message_ids=set(state["summarized_message_ids"]),
    last_summarized_message_id=state["last_summarized_message_id"])

model.output = "FAKE_SUMMARY_V2"
batch_two = make_messages("second", 2)
second = run(batch_two, model, rehydrated)
assert len(model.calls) == 2
assert set(ids(model.calls[1])) == {"second-0", "second-1"}
second_prompt = "\n".join(str(message.content) for message in model.calls[1])
assert "FAKE_SUMMARY_V1" in second_prompt
assert "SYNTHETIC_first" not in second_prompt
assert second.running_summary is not None
assert len(second.running_summary.summarized_message_ids) == 4

# The upstream documented cumulative-history interface also avoids rereading old
# body text into the model when the last summarized ID is present.
cumulative_model = FakeHarness("FAKE_CUMULATIVE_SUMMARY")
cumulative = run(batch_one + batch_two, cumulative_model, rehydrated)
assert len(cumulative_model.calls) == 1
assert set(ids(cumulative_model.calls[0])) == {"second-0", "second-1"}

# Threshold may select a range larger than max_tokens. trim_messages discards its
# beginning, but RunningSummary still records the original range as summarized.
trim_model = FakeHarness("FAKE_TRIM_SUMMARY")
oversized = make_messages("oversized", 5, 100)
trimmed = run(oversized, trim_model, max_tokens=180,
              max_tokens_before_summary=300, max_summary_tokens=20)
assert trimmed.running_summary is not None and len(trim_model.calls) == 1
seen_ids = set(ids(trim_model.calls[0]))
claimed_ids = trimmed.running_summary.summarized_message_ids
missing = sorted(claimed_ids - seen_ids)
assert missing, "Expected upstream trim/coverage mismatch was not reproduced"

# max_summary_tokens budgets context; it does not enforce provider output size.
long_model = FakeHarness("S" * 200)
long_result = run(batch_one, long_model)
assert long_result.running_summary is not None
assert len(long_result.running_summary.summary) == 200

failure_model = FakeHarness(fail=True)
failure = None
try:
    run(batch_one, failure_model)
except RuntimeError as error:
    failure = str(error)
assert failure == "SYNTHETIC_PROVIDER_FAILURE" and len(failure_model.calls) == 1

# The same single generation can carry title + summary. The real Harness adapter
# must enforce its existing output schema; this fake only proves the API accepts
# custom prompts and roundtrips the JSON string through RunningSummary.
metadata_payload = {"title": "Synthetic title", "summary": "Synthetic reference index"}
schema_model = FakeHarness(json.dumps(metadata_payload))
initial_schema_prompt = ChatPromptTemplate.from_messages([
    ("placeholder", "{messages}"),
    ("user", "Return a JSON object with string title and summary fields."),
])
existing_schema_prompt = ChatPromptTemplate.from_messages([
    ("placeholder", "{messages}"),
    ("user", "Previous JSON metadata: {existing_summary}\nUpdate its title and summary using the new messages; return JSON."),
])
schema_first = run(batch_one, schema_model, initial_summary_prompt=initial_schema_prompt,
                   existing_summary_prompt=existing_schema_prompt)
schema_second = run(batch_two, schema_model, schema_first.running_summary,
                    initial_summary_prompt=initial_schema_prompt,
                    existing_summary_prompt=existing_schema_prompt)
parsed_metadata = json.loads(schema_second.running_summary.summary)
assert parsed_metadata == metadata_payload and len(schema_model.calls) == 2
assert all(isinstance(parsed_metadata[key], str) for key in ("title", "summary"))
assert metadata_payload["title"] in str(schema_model.calls[1][-1].content)

source_file = Path(inspect.getsourcefile(summarize_messages))
site = Path(importlib.metadata.distribution("langmem").locate_file(""))
site_bytes = sum(path.stat().st_size for path in site.rglob("*") if path.is_file())
distributions = sorted((dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions())
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
peak_bytes = peak if sys.platform == "darwin" else peak * 1024
result = {
    "scope": "synthetic mechanism only; no model, provider, database or private history",
    "unit_warning": "All budget values in this probe are character units, not model tokens.",
    "python": platform.python_version(),
    "langmem": importlib.metadata.version("langmem"),
    "installed_source_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
    "zero_threshold_calls": len(small_model.calls),
    "two_batches": {
        "calls_total": len(model.calls), "calls_per_batch": [1, 1],
        "first_seen_ids": ids(model.calls[0]), "second_seen_ids": ids(model.calls[1]),
        "second_contains_previous_summary": "FAKE_SUMMARY_V1" in second_prompt,
        "second_contains_previous_raw_body": "SYNTHETIC_first" in second_prompt,
        "state_roundtrip": True,
        "summary_ids": sorted(second.running_summary.summarized_message_ids),
        "last_id": second.running_summary.last_summarized_message_id,
        "second_input_units_with_fixed_prompt": units(model.calls[1]),
    },
    "cumulative_history_second_seen_ids": ids(cumulative_model.calls[0]),
    "over_budget": {
        "seen_ids": sorted(seen_ids), "claimed_summarized_ids": sorted(claimed_ids),
        "claimed_but_unseen_ids": missing,
        "seen_input_units_with_fixed_prompt": units(trim_model.calls[0]),
        "max_tokens_argument_units": 180,
    },
    "output_cap": {"max_summary_tokens_argument_units": 64,
                   "actual_summary_units": len(long_result.running_summary.summary)},
    "failure": {"propagated_error": failure, "fake_calls": len(failure_model.calls)},
    "title_summary_bridge": {
        "calls_per_batch": [1, 1], "mapped_metadata": parsed_metadata,
        "custom_initial_and_existing_prompts": True,
        "prior_json_in_second_prompt": True,
        "schema_enforcement_note": "The fake returns valid JSON by construction; real Harness output-schema enforcement and quality remain untested.",
    },
    "footprint": {"distribution_count": len(distributions),
                  "site_packages_apparent_bytes_after_import": site_bytes,
                  "single_process_import_seconds": import_seconds,
                  "single_process_peak_rss_bytes": peak_bytes},
}
print(json.dumps(result, indent=2, sort_keys=True))
