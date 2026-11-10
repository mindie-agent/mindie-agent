"""[Role] Check the releases that installed component updaters actually discover.

[Invariants] Historical channels and adapter pins never substitute for latest
component heads. Validation executes the production consumer without relaxation.
[Timeouts & Locks] The caller supplies a catalog with a bounded network budget.
[Side-Effect Policy] Public reads and an explicitly owned temporary HTTP cache.
"""
from __future__ import annotations


def verify_latest_components(catalog, *, names=None):
    from mindie_knowledge.runtime_inventory import COMPONENTS

    errors = []
    for name in COMPONENTS if names is None else names:
        try:
            catalog.latest(name, force=True)
        except TimeoutError:
            raise
        except (ValueError, KeyError, OSError) as error:
            errors.append(
                f"{COMPONENTS[name]}: latest formal release rejected by the installed "
                f"consumer ({type(error).__name__}): {error}")
    return errors


def verify_current_release_heads():
    from tempfile import TemporaryDirectory

    from mindie_knowledge.component_releases import Catalog

    with TemporaryDirectory(prefix="mindie-latest-release-check-") as directory:
        return verify_latest_components(Catalog(cache=directory, budget=300))
