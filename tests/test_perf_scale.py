"""Scale / performance guardrail tests.

Soft ceilings with ~10x headroom. The goal is catching accidental O(n²)
regressions — not benchmarking. Failures mean "something got much worse",
not "this is 5% slower than yesterday".

Marked ``@pytest.mark.perf`` — excluded from the default pytest run via
``pyproject.toml``'s ``addopts``. Run explicitly with:

    uv run python -m pytest tests/test_perf_scale.py -m perf -v
"""

from __future__ import annotations

import time

import pytest

from anxwritter import ANXChart, Icon, Link, ANXValidationError


pytestmark = pytest.mark.perf


def _elapsed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - t0


class TestEntityScale:
    def test_10k_entities_builds_under_budget(self):
        """10,000 icons + to_xml must complete in under 10 seconds.

        Current baseline on a developer workstation: ~1-2s. The 10s budget
        is intentionally generous so this isn't hardware-flaky.
        """
        chart = ANXChart()
        chart.add_all(
            Icon(id=f"E{i:05d}", type="Person") for i in range(10_000)
        )
        _xml, elapsed = _elapsed(chart.to_xml)
        assert elapsed < 10.0, (
            f"10k-entity build took {elapsed:.2f}s, budget is 10s. "
            f"Possible O(n^2) regression."
        )
        assert len(chart._entities) == 10_000

    def test_10k_entities_with_auto_color_builds_under_budget(self):
        """entity_auto_color=True on 10k entities — the HSV distribution
        step has historically been an O(n^2) risk."""
        chart = ANXChart(settings={"extra_cfg": {"entity_auto_color": True}})
        chart.add_all(
            Icon(id=f"E{i:05d}", type="Person") for i in range(10_000)
        )
        _xml, elapsed = _elapsed(chart.to_xml)
        assert elapsed < 15.0, (
            f"10k-entity auto-color build took {elapsed:.2f}s, budget is 15s."
        )


class TestLinkScale:
    def test_5k_entities_50k_links_under_budget(self):
        """5k entities with 50k links — links are 10x entities, exercises the
        link offset / deduplication code path."""
        chart = ANXChart()
        n_entities = 5_000
        chart.add_all(
            Icon(id=f"E{i:05d}", type="Person") for i in range(n_entities)
        )

        # 50k links: each link between random-ish consecutive pairs
        links = []
        for i in range(50_000):
            src = i % n_entities
            dst = (i + 1) % n_entities
            links.append(
                Link(from_id=f"E{src:05d}", to_id=f"E{dst:05d}", type="Rel")
            )
        chart.add_all(links)

        _xml, elapsed = _elapsed(chart.to_xml)
        assert elapsed < 30.0, (
            f"5k-entity / 50k-link build took {elapsed:.2f}s, budget is 30s. "
            f"Possible O(n^2) regression in link handling."
        )
        assert len(chart._links) == 50_000

    def test_link_offset_auto_spacing_scales(self):
        """1k entities + 10k parallel links between overlapping pairs.

        The auto-offset computation must group links by entity pair and
        assign offsets — a naive O(n^2) implementation would be ~50M ops.
        """
        chart = ANXChart(settings={"extra_cfg": {"link_arc_offset": 20}})
        n_entities = 1_000
        chart.add_all(
            Icon(id=f"E{i:04d}", type="Person") for i in range(n_entities)
        )

        # 10k links, many sharing entity pairs
        links = []
        for i in range(10_000):
            src = i % n_entities
            dst = (src + 1) % n_entities
            links.append(
                Link(from_id=f"E{src:04d}", to_id=f"E{dst:04d}", type="Rel")
            )
        chart.add_all(links)

        _xml, elapsed = _elapsed(chart.to_xml)
        assert elapsed < 20.0, (
            f"Link auto-offset with 10k overlapping links took {elapsed:.2f}s, "
            f"budget is 20s. Possible O(n^2) regression in compute_link_offsets."
        )


class TestValueEnforcementScale:
    """Value enforcement guardrails (1.17.0)."""

    def test_10k_entities_with_validators(self):
        """10k entities + 5 validators (mix of pattern + allowed_values) +
        AC.enforce.pattern. validate() must stay roughly proportional —
        budget 10x slack on baseline."""
        chart = ANXChart()
        chart.apply_config({
            "entity_types": [
                {"name": "Person", "icon_file": "person",
                 "enforce": {"id_pattern": r"^E\d+$",
                             "id_pattern_description": "E + digits",
                             "required_attributes": ["CPF"]}},
            ],
            "attribute_classes": [
                {"name": "CPF", "type": "text",
                 "enforce": {"pattern": r"^\d{11}$", "description": "11 digits"}},
                {"name": "Status", "type": "text",
                 "enforce": {"allowed_values": ["Active", "Inactive"]}},
            ],
            "validators": [
                {"entity_type": "Person", "attribute": "CPF",
                 "pattern": r"^[1-9]\d{10}$",
                 "description": "first digit non-zero"},
                {"entity_type": "Person", "attribute": "Status",
                 "allowed_values": ["Active", "Inactive"]},
                {"entity_type": "Person", "attribute": "Country",
                 "allowed_values": ["BR", "US", "UK"]},
            ],
        })
        chart.add_all(
            Icon(id=f"E{i:05d}", type="Person",
                 attributes={"CPF": f"{i+1000000000:011d}",
                             "Status": "Active",
                             "Country": "BR"})
            for i in range(10_000)
        )
        _result, elapsed = _elapsed(chart.validate)
        # Pattern checks are O(n) on entities; should complete in under 5s
        # for 10k entities × 3 attributes × 2 rule sources.
        assert elapsed < 10.0, (
            f"Validation with 10k entities + 5 validators took {elapsed:.2f}s, "
            f"budget is 10s. Possible O(n^2) regression in value enforcement."
        )

    def test_smart_truncation_handles_many_failures(self):
        """A 50k-row failure should not blow up message rendering."""
        chart = ANXChart()
        chart.apply_config({
            "entity_types": [{"name": "P", "icon_file": "person",
                              "enforce": {"id_pattern": r"^\d+$",
                                          "id_pattern_description": "digits"}}],
        })
        for i in range(5_000):
            chart.add_icon(id=f"bad-{i}", type="P")
        errors = chart.validate()
        assert len(errors) == 5_000
        # str(ANXValidationError) must finish quickly even at this scale.
        _msg, elapsed = _elapsed(lambda: str(ANXValidationError(errors)))
        assert elapsed < 1.0, (
            f"str(ANXValidationError(5000 errors)) took {elapsed:.2f}s, "
            f"budget is 1s. Possible O(n^2) in smart truncation."
        )
