import json
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

import orchestrator
from orchestrator import (
    load_json, save_json, update_frequency_log,
    gaps_above_threshold, already_deferred, main,
)
from tests.conftest import (
    SAMPLE_WORKFLOW, SAMPLE_CLUSTER, SAMPLE_TRANSLATOR_RESULT,
    SAMPLE_AUDIT_FAIL, SAMPLE_AUDIT_PASS,
    SAMPLE_PM_ACCEPT, SAMPLE_PM_REJECT, SAMPLE_PM_DEFER,
    SAMPLE_MANIFEST,
)


# =========================================================================
# Helper function tests
# =========================================================================

class TestLoadJson:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "val"}')
        assert load_json(f) == {"key": "val"}

    def test_missing_file_no_default(self, tmp_path):
        f = tmp_path / "nope.json"
        assert load_json(f) == {}

    def test_missing_file_with_default(self, tmp_path):
        f = tmp_path / "nope.json"
        assert load_json(f, default={"x": 1}) == {"x": 1}

    def test_missing_file_with_none_default_returns_empty_dict(self, tmp_path):
        """When default=None explicitly, falls through to the {} fallback."""
        f = tmp_path / "nope.json"
        assert load_json(f, default=None) == {}


class TestSaveJson:
    def test_writes_file(self, tmp_path):
        f = tmp_path / "out.json"
        save_json(f, {"a": 1})
        assert json.loads(f.read_text()) == {"a": 1}

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "deep" / "nested" / "out.json"
        save_json(f, [1, 2, 3])
        assert json.loads(f.read_text()) == [1, 2, 3]

    def test_overwrites_existing(self, tmp_path):
        f = tmp_path / "out.json"
        f.write_text('{"old": true}')
        save_json(f, {"new": True})
        assert json.loads(f.read_text()) == {"new": True}


class TestUpdateFrequencyLog:
    def test_new_primitive(self):
        log = {}
        result = update_frequency_log(log, ["import"], {"FP&A Analyst"}, "import-compare")
        assert "import" in result
        assert result["import"]["count"] == 1
        assert "FP&A Analyst" in result["import"]["roles"]
        assert "import-compare" in result["import"]["canonical_labels"]
        assert result["import"]["first_seen"] == result["import"]["last_seen"]

    def test_existing_primitive_increments(self):
        log = {
            "import": {
                "count": 2,
                "roles": ["FP&A Analyst"],
                "canonical_labels": ["import-compare"],
                "first_seen": "2026-01-01",
                "last_seen": "2026-01-01",
            }
        }
        result = update_frequency_log(log, ["import"], {"Controller"}, "import-compare")
        assert result["import"]["count"] == 3
        assert "Controller" in result["import"]["roles"]
        assert "FP&A Analyst" in result["import"]["roles"]

    def test_adds_new_label(self):
        log = {
            "import": {
                "count": 1,
                "roles": ["FP&A Analyst"],
                "canonical_labels": ["import-compare"],
                "first_seen": "2026-01-01",
                "last_seen": "2026-01-01",
            }
        }
        result = update_frequency_log(log, ["import"], {"FP&A Analyst"}, "import-pivot")
        assert "import-pivot" in result["import"]["canonical_labels"]
        assert "import-compare" in result["import"]["canonical_labels"]

    def test_does_not_duplicate_label(self):
        log = {
            "import": {
                "count": 1,
                "roles": [],
                "canonical_labels": ["import-compare"],
                "first_seen": "2026-01-01",
                "last_seen": "2026-01-01",
            }
        }
        result = update_frequency_log(log, ["import"], set(), "import-compare")
        assert result["import"]["canonical_labels"].count("import-compare") == 1

    def test_multiple_primitives_at_once(self):
        log = {}
        result = update_frequency_log(log, ["import", "chart"], {"FP&A Analyst"}, "import-chart")
        assert "import" in result
        assert "chart" in result
        assert result["import"]["count"] == 1
        assert result["chart"]["count"] == 1


class TestGapsAboveThreshold:
    def test_above_threshold(self, monkeypatch):
        monkeypatch.setattr(orchestrator, "FREQUENCY_THRESHOLD", 3)
        monkeypatch.setattr(orchestrator, "ROLE_THRESHOLD", 2)
        log = {
            "import": {"count": 5, "roles": ["A", "B", "C"], "canonical_labels": ["x"]},
        }
        result = gaps_above_threshold(log)
        assert len(result) == 1
        assert result[0]["gap_primitive"] == "import"

    def test_below_count_threshold(self, monkeypatch):
        monkeypatch.setattr(orchestrator, "FREQUENCY_THRESHOLD", 3)
        monkeypatch.setattr(orchestrator, "ROLE_THRESHOLD", 2)
        log = {
            "import": {"count": 2, "roles": ["A", "B"], "canonical_labels": ["x"]},
        }
        assert gaps_above_threshold(log) == []

    def test_below_role_threshold(self, monkeypatch):
        monkeypatch.setattr(orchestrator, "FREQUENCY_THRESHOLD", 3)
        monkeypatch.setattr(orchestrator, "ROLE_THRESHOLD", 2)
        log = {
            "import": {"count": 5, "roles": ["A"], "canonical_labels": ["x"]},
        }
        assert gaps_above_threshold(log) == []

    def test_empty_log(self, monkeypatch):
        monkeypatch.setattr(orchestrator, "FREQUENCY_THRESHOLD", 1)
        monkeypatch.setattr(orchestrator, "ROLE_THRESHOLD", 1)
        assert gaps_above_threshold({}) == []

    def test_mixed_above_and_below(self, monkeypatch):
        monkeypatch.setattr(orchestrator, "FREQUENCY_THRESHOLD", 2)
        monkeypatch.setattr(orchestrator, "ROLE_THRESHOLD", 1)
        log = {
            "import": {"count": 3, "roles": ["A"], "canonical_labels": ["x"]},
            "chart": {"count": 1, "roles": ["A"], "canonical_labels": ["y"]},
        }
        result = gaps_above_threshold(log)
        assert len(result) == 1
        assert result[0]["gap_primitive"] == "import"


class TestAlreadyDeferred:
    def test_not_deferred(self):
        assert already_deferred("import", [], {}) is False

    def test_deferred_frequency_not_increased(self):
        queue = [{"primitive": "import", "frequency_at_deferral": 3}]
        log = {"import": {"count": 3}}
        assert already_deferred("import", queue, log) is True

    def test_deferred_frequency_increased(self):
        queue = [{"primitive": "import", "frequency_at_deferral": 3}]
        log = {"import": {"count": 5}}
        assert already_deferred("import", queue, log) is False

    def test_different_primitive_in_queue(self):
        queue = [{"primitive": "chart", "frequency_at_deferral": 2}]
        log = {"import": {"count": 5}}
        assert already_deferred("import", queue, log) is False

    def test_deferred_primitive_not_in_log(self):
        queue = [{"primitive": "import", "frequency_at_deferral": 3}]
        assert already_deferred("import", queue, {}) is True


# =========================================================================
# main() integration tests
# =========================================================================

@pytest.fixture
def pipeline_env(tmp_path, monkeypatch):
    """Set up isolated paths and small config for orchestrator.main()."""
    manifest_path = tmp_path / "manifest" / "vireo_manifest.json"
    freq_log_path = tmp_path / "state" / "frequency_log.json"
    defer_path = tmp_path / "state" / "defer_queue.json"
    output_dir = tmp_path / "output"

    monkeypatch.setattr(orchestrator, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(orchestrator, "FREQUENCY_LOG_PATH", freq_log_path)
    monkeypatch.setattr(orchestrator, "DEFER_QUEUE_PATH", defer_path)
    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", output_dir)

    # Small config for fast tests
    monkeypatch.setattr(orchestrator, "ROLES", [("FP&A Analyst", 1.0)])
    monkeypatch.setattr(orchestrator, "ITERATIONS_PER_ROLE", 1)
    monkeypatch.setattr(orchestrator, "WORKFLOWS_PER_CALL", 2)
    monkeypatch.setattr(orchestrator, "FREQUENCY_THRESHOLD", 1)
    monkeypatch.setattr(orchestrator, "ROLE_THRESHOLD", 1)

    # Write manifest
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(SAMPLE_MANIFEST))

    return {
        "tmp_path": tmp_path,
        "manifest_path": manifest_path,
        "freq_log_path": freq_log_path,
        "defer_path": defer_path,
        "output_dir": output_dir,
    }


def _scope_response():
    return json.dumps({"workflows": [SAMPLE_WORKFLOW]})


def _canonical_response():
    return json.dumps({"clusters": [SAMPLE_CLUSTER]})


def _translator_response():
    return json.dumps({"results": [SAMPLE_TRANSLATOR_RESULT]})


def _audit_response_fail():
    return json.dumps({"results": [SAMPLE_AUDIT_FAIL]})


def _audit_response_pass():
    return json.dumps({"results": [SAMPLE_AUDIT_PASS]})


def _pm_response_accept():
    return json.dumps({"decisions": [SAMPLE_PM_ACCEPT]})


def _pm_response_reject():
    return json.dumps({"decisions": [SAMPLE_PM_REJECT]})


def _pm_response_defer():
    return json.dumps({"decisions": [SAMPLE_PM_DEFER]})


def _pm_response_mixed():
    return json.dumps({"decisions": [SAMPLE_PM_ACCEPT, SAMPLE_PM_REJECT, SAMPLE_PM_DEFER]})


def _mock_all_agents(monkeypatch):
    """Patch all agent classes and return mock instances."""
    mocks = {}
    for name in ["ScopeAgent", "CanonicalizerAgent", "TranslatorAgent",
                  "AuditorAgent", "PMAgent", "SpecWriterAgent"]:
        cls_mock = MagicMock()
        monkeypatch.setattr(orchestrator, name, cls_mock)
        mocks[name] = cls_mock
    return mocks


class TestMainNoManifest:
    def test_exits_early_when_manifest_missing(self, pipeline_env):
        pipeline_env["manifest_path"].unlink()
        agents = _mock_all_agents(pytest.MonkeyPatch())
        # Even without mocking agents, main should exit before touching them
        # But we need to monkeypatch the agent classes because they're imported.
        # Actually, main will fail at load_json returning {} which is falsy.
        main()
        assert not pipeline_env["output_dir"].exists()

    def test_exits_early_when_manifest_empty(self, pipeline_env):
        pipeline_env["manifest_path"].write_text("{}")
        main()
        assert not pipeline_env["output_dir"].exists()


class TestMainScopeFailures:
    def test_no_workflows_generated(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        scope_inst = mocks["ScopeAgent"].return_value
        scope_inst.build_user_prompt.return_value = "prompt"
        scope_inst.ask.side_effect = Exception("API error")
        main()
        assert not pipeline_env["output_dir"].exists()

    def test_scope_json_parse_error_continues(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        scope_inst = mocks["ScopeAgent"].return_value
        scope_inst.build_user_prompt.return_value = "prompt"
        # First call fails, but since ITERATIONS_PER_ROLE=1 and only 1 role,
        # no workflows are generated and main exits
        scope_inst.ask.return_value = "not valid json"
        main()
        assert not pipeline_env["output_dir"].exists()


class TestMainCanonicalizationFailure:
    def test_exits_on_canonicalization_error(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        # Scope succeeds
        scope_inst = mocks["ScopeAgent"].return_value
        scope_inst.build_user_prompt.return_value = "prompt"
        scope_inst.ask.return_value = _scope_response()
        # Canonicalizer fails
        canon_inst = mocks["CanonicalizerAgent"].return_value
        canon_inst.build_user_prompt.return_value = "prompt"
        canon_inst.ask.side_effect = Exception("API error")
        main()
        assert not pipeline_env["output_dir"].exists()


class TestMainTranslationFailure:
    def test_exits_on_translation_error(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        scope_inst = mocks["ScopeAgent"].return_value
        scope_inst.build_user_prompt.return_value = "prompt"
        scope_inst.ask.return_value = _scope_response()
        canon_inst = mocks["CanonicalizerAgent"].return_value
        canon_inst.build_user_prompt.return_value = "prompt"
        canon_inst.ask.return_value = _canonical_response()
        # Translator fails
        trans_inst = mocks["TranslatorAgent"].return_value
        trans_inst.build_user_prompt.return_value = "prompt"
        trans_inst.ask.side_effect = Exception("API error")
        main()
        assert not pipeline_env["output_dir"].exists()


class TestMainAuditFailure:
    def test_exits_on_audit_error(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        scope_inst = mocks["ScopeAgent"].return_value
        scope_inst.build_user_prompt.return_value = "prompt"
        scope_inst.ask.return_value = _scope_response()
        canon_inst = mocks["CanonicalizerAgent"].return_value
        canon_inst.build_user_prompt.return_value = "prompt"
        canon_inst.ask.return_value = _canonical_response()
        trans_inst = mocks["TranslatorAgent"].return_value
        trans_inst.build_user_prompt.return_value = "prompt"
        trans_inst.ask.return_value = _translator_response()
        # Auditor fails
        audit_inst = mocks["AuditorAgent"].return_value
        audit_inst.build_user_prompt.return_value = "prompt"
        audit_inst.ask.return_value = "not json"
        main()
        assert not pipeline_env["output_dir"].exists()


def _setup_through_audit(mocks, audit_response):
    """Configure mock agents through the audit phase."""
    scope_inst = mocks["ScopeAgent"].return_value
    scope_inst.build_user_prompt.return_value = "prompt"
    scope_inst.ask.return_value = _scope_response()

    canon_inst = mocks["CanonicalizerAgent"].return_value
    canon_inst.build_user_prompt.return_value = "prompt"
    canon_inst.ask.return_value = _canonical_response()

    trans_inst = mocks["TranslatorAgent"].return_value
    trans_inst.build_user_prompt.return_value = "prompt"
    trans_inst.ask.return_value = _translator_response()

    audit_inst = mocks["AuditorAgent"].return_value
    audit_inst.build_user_prompt.return_value = "prompt"
    audit_inst.ask.return_value = audit_response


class TestMainAllPassAudit:
    def test_no_gaps_exits_after_frequency(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_pass())
        main()
        # No spec files written
        assert not pipeline_env["output_dir"].exists() or len(list(pipeline_env["output_dir"].iterdir())) == 0
        # PM was never called
        mocks["PMAgent"].return_value.ask.assert_not_called()


class TestMainFrequencyTracking:
    def test_no_matching_cluster_skipped(self, pipeline_env, monkeypatch):
        """Audit result references a label not in canonical clusters."""
        mocks = _mock_all_agents(monkeypatch)
        # Audit result with a different label than what canonicalizer returned
        mismatched_audit = {
            **SAMPLE_AUDIT_FAIL,
            "canonical_label": "nonexistent-label",
        }
        _setup_through_audit(mocks, json.dumps({"results": [mismatched_audit]}))
        main()
        # Frequency log should be empty (gap wasn't tracked)
        if pipeline_env["freq_log_path"].exists():
            log = json.loads(pipeline_env["freq_log_path"].read_text())
            assert log == {}


class TestMainBelowThreshold:
    def test_gaps_below_threshold_not_escalated(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        # Set high thresholds so gaps don't escalate
        monkeypatch.setattr(orchestrator, "FREQUENCY_THRESHOLD", 100)
        monkeypatch.setattr(orchestrator, "ROLE_THRESHOLD", 50)
        main()
        mocks["PMAgent"].return_value.ask.assert_not_called()


class TestMainAlreadyDeferredFiltered:
    def test_deferred_gap_not_re_evaluated(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        # Pre-populate defer queue with the gap at current frequency
        defer_data = {
            "deferred": [{
                "primitive": "import",
                "reason": "previously deferred",
                "deferred_at": "2026-01-01",
                "frequency_at_deferral": 999,  # high enough to suppress
            }]
        }
        pipeline_env["defer_path"].parent.mkdir(parents=True, exist_ok=True)
        pipeline_env["defer_path"].write_text(json.dumps(defer_data))
        main()
        mocks["PMAgent"].return_value.ask.assert_not_called()


class TestMainPMFailure:
    def test_exits_on_pm_error(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = "not json"
        main()
        assert not pipeline_env["output_dir"].exists() or len(list(pipeline_env["output_dir"].iterdir())) == 0


class TestMainPMDecisions:
    def test_all_rejected(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = _pm_response_reject()
        main()
        assert not pipeline_env["output_dir"].exists() or len(list(pipeline_env["output_dir"].iterdir())) == 0

    def test_all_deferred(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = _pm_response_defer()
        main()
        # Defer queue should be updated
        defer_data = json.loads(pipeline_env["defer_path"].read_text())
        assert len(defer_data["deferred"]) == 1
        assert defer_data["deferred"][0]["primitive"] == "chart"

    def test_mixed_decisions(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = _pm_response_mixed()
        spec_inst = mocks["SpecWriterAgent"].return_value
        spec_inst.build_user_prompt.return_value = "prompt"
        spec_inst.ask.return_value = "# Import Spec\n\nMarkdown content"
        main()
        # Accepted gap should have a spec file
        spec_file = pipeline_env["output_dir"] / "import_spec.md"
        assert spec_file.exists()
        assert "Import Spec" in spec_file.read_text()
        # Deferred gap in queue
        defer_data = json.loads(pipeline_env["defer_path"].read_text())
        deferred_prims = [d["primitive"] for d in defer_data["deferred"]]
        assert "chart" in deferred_prims


class TestMainHappyPath:
    def test_full_pipeline_writes_spec(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = _pm_response_accept()
        spec_inst = mocks["SpecWriterAgent"].return_value
        spec_inst.build_user_prompt.return_value = "prompt"
        spec_inst.ask.return_value = "# Import\n\nThis is the spec."
        main()
        spec_file = pipeline_env["output_dir"] / "import_spec.md"
        assert spec_file.exists()
        content = spec_file.read_text()
        assert "Import" in content
        assert "This is the spec." in content

    def test_frequency_log_persisted(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = _pm_response_accept()
        spec_inst = mocks["SpecWriterAgent"].return_value
        spec_inst.build_user_prompt.return_value = "prompt"
        spec_inst.ask.return_value = "# Spec"
        main()
        log = json.loads(pipeline_env["freq_log_path"].read_text())
        assert "import" in log
        assert log["import"]["count"] >= 1


class TestMainSpecWriterFailure:
    def test_continues_after_spec_error(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = _pm_response_accept()
        spec_inst = mocks["SpecWriterAgent"].return_value
        spec_inst.build_user_prompt.return_value = "prompt"
        spec_inst.ask.side_effect = Exception("Spec generation failed")
        # Should not raise — error is caught
        main()
        # No spec file written
        output_files = list(pipeline_env["output_dir"].iterdir()) if pipeline_env["output_dir"].exists() else []
        assert len(output_files) == 0


class TestMainPreExistingState:
    def test_loads_existing_frequency_log(self, pipeline_env, monkeypatch):
        mocks = _mock_all_agents(monkeypatch)
        # Pre-populate frequency log
        existing_log = {
            "import": {
                "count": 2,
                "roles": ["Treasury Analyst"],
                "canonical_labels": ["import-pivot"],
                "first_seen": "2026-01-01",
                "last_seen": "2026-01-01",
            }
        }
        pipeline_env["freq_log_path"].parent.mkdir(parents=True, exist_ok=True)
        pipeline_env["freq_log_path"].write_text(json.dumps(existing_log))
        _setup_through_audit(mocks, _audit_response_fail())
        pm_inst = mocks["PMAgent"].return_value
        pm_inst.build_user_prompt.return_value = "prompt"
        pm_inst.ask.return_value = _pm_response_accept()
        spec_inst = mocks["SpecWriterAgent"].return_value
        spec_inst.build_user_prompt.return_value = "prompt"
        spec_inst.ask.return_value = "# Spec"
        main()
        log = json.loads(pipeline_env["freq_log_path"].read_text())
        # Count should have increased from pre-existing 2
        assert log["import"]["count"] == 3
        # Both roles should be present
        assert "Treasury Analyst" in log["import"]["roles"]
        assert "FP&A Analyst" in log["import"]["roles"]
