"""Tests for model __repr__ methods to boost coverage."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.evolution_models import (
    EvolutionChangelog,
    EvolutionPath,
    EvolutionSnapshot,
    SkillTimeseries,
)
from app.models.learning_models import LearningPlan, LearningProgress, SkillPrerequisite
from app.models.pipeline_models import DataSourceRecord, PipelineRun


class TestEvolutionModels:
    def test_snapshot_repr(self):
        snap = EvolutionSnapshot(
            position_name="Dev",
            snapshot_date=datetime.now(UTC),
            required_skills=[{"name": "Python"}],
        )
        r = repr(snap)
        assert "EvolutionSnapshot" in r
        assert "Dev" in r

    def test_changelog_repr(self):
        log = EvolutionChangelog(
            position_name="Dev",
            skill_name="Python",
            change_type="added",
        )
        r = repr(log)
        assert "EvolutionChangelog" in r
        assert "Python" in r

    def test_path_repr(self):
        path = EvolutionPath(
            source_position="Junior",
            target_position="Senior",
            similarity=0.85,
        )
        r = repr(path)
        assert "EvolutionPath" in r

    def test_timeseries_repr(self):
        ts = SkillTimeseries(
            skill_name="Python",
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
            frequency=3,
            source_count=5,
        )
        r = repr(ts)
        assert "SkillTimeseries" in r


class TestLearningModels:
    def test_plan_repr(self):
        plan = LearningPlan(
            user_id="user1",
            position="Dev",
            skills=[{"name": "Python"}],
        )
        r = repr(plan)
        assert "LearningPlan" in r

    def test_progress_repr(self):
        progress = LearningProgress(
            plan_id=uuid.uuid4(),
            skill_name="Python",
            importance="required",
        )
        r = repr(progress)
        assert "LearningProgress" in r

    def test_skill_prerequisite_repr(self):
        prereq = SkillPrerequisite(
            skill="FastAPI",
            prerequisite="Python",
            strength=0.9,
        )
        r = repr(prereq)
        assert "SkillPrerequisite" in r
        assert "FastAPI" in r


class TestPipelineModels:
    def test_datasource_repr(self):
        ds = DataSourceRecord(
            name="test_source",
            source_type="crawl",
            status="active",
            authority_score=0.8,
            total_records=10,
            valid_records=8,
        )
        r = repr(ds)
        assert "DataSourceRecord" in r

    def test_pipeline_run_repr(self):
        run = PipelineRun(
            id=uuid.uuid4(),
            run_type="full",
            status="running",
            started_at=datetime.now(UTC),
            total_records=0,
            new_records=0,
            updated_records=0,
            quality_score=0.0,
        )
        r = repr(run)
        assert "PipelineRun" in r
