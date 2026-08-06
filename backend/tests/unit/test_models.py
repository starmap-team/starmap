"""Lightweight tests to ensure model definitions are importable and instantiatable.

These tests exist primarily to exercise the model module for coverage - the
classes below are SQLAlchemy ORM models and Pydantic/v2 schemas that are
validated structurally at class-definition time.
"""

import uuid

from sqlalchemy.orm import DeclarativeBase

from app.models import (
    Base,
    ExtractionEvaluationRecord,
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    RawJDRecord,
    SkillAliasRecord,
    SkillRecord,
    SystemConfig,
)


class TestModelImports:
    """Verify all model classes are importable."""

    def test_base_is_declarative(self):
        """Base should be a SQLAlchemy declarative base."""
        assert isinstance(Base, type)
        assert issubclass(Base, DeclarativeBase)

    def test_all_models_are_subclasses(self):
        """All model classes should inherit from Base."""
        models = [
            ExtractionEvaluationRecord,
            JDExtractionRecord,
            PositionRecord,
            PositionSkillRelation,
            RawJDRecord,
            SkillAliasRecord,
            SkillRecord,
            SystemConfig,
        ]
        for model in models:
            assert issubclass(model, Base), f"{model.__name__} does not inherit from Base"

    def test_model_tablenames_defined(self):
        """Each model should have a __tablename__."""
        models = [
            ExtractionEvaluationRecord,
            JDExtractionRecord,
            PositionRecord,
            PositionSkillRelation,
            RawJDRecord,
            SkillAliasRecord,
            SkillRecord,
            SystemConfig,
        ]
        for model in models:
            assert hasattr(model, "__tablename__"), f"{model.__name__} missing __tablename__"
            assert isinstance(model.__tablename__, str)


class TestModelInstantiation:
    """Verify model instances can be created."""

    def test_jd_extraction_record(self):
        """JDExtractionRecord can be instantiated with required fields."""
        record = JDExtractionRecord(
            jd_content="test jd content",
            job_title="Software Engineer",
            extracted_skills={"python": 0.9},
        )
        assert record.jd_content == "test jd content"
        assert record.job_title == "Software Engineer"
        assert record.extracted_skills == {"python": 0.9}

    def test_raw_jd_record(self):
        """RawJDRecord can be instantiated."""
        record = RawJDRecord(
            raw_text="raw job description text",
            source_platform="linkedin",
        )
        assert record.raw_text == "raw job description text"
        assert record.source_platform == "linkedin"

    def test_skill_record(self):
        """SkillRecord can be instantiated."""
        record = SkillRecord(
            name="Python",
            category="hard_skill",
        )
        assert record.name == "Python"
        assert record.category == "hard_skill"

    def test_skill_alias_record(self):
        """SkillAliasRecord can be instantiated."""
        record = SkillAliasRecord(
            alias="py",
            standard_name="Python",
        )
        assert record.alias == "py"
        assert record.standard_name == "Python"

    def test_position_record(self):
        """PositionRecord can be instantiated."""
        record = PositionRecord(
            name="Backend Engineer",
        )
        assert record.name == "Backend Engineer"

    def test_position_skill_relation(self):
        """PositionSkillRelation can be instantiated."""
        position_id = uuid.uuid4()
        skill_id = uuid.uuid4()
        relation = PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_id,
        )
        assert relation.position_id == position_id
        assert relation.skill_id == skill_id

    def test_extraction_evaluation_record(self):
        """ExtractionEvaluationRecord can be instantiated."""
        record = ExtractionEvaluationRecord(
            golden_id="golden-001",
        )
        assert record.golden_id == "golden-001"

    def test_system_config_record(self):
        """SystemConfig can be instantiated."""
        record = SystemConfig(
            config_key="test_key",
            config_value={"nested": "value"},
        )
        assert record.config_key == "test_key"


class TestModelRegistryCompleteness:
    """NEW-14: 全部 ORM 模型必须在 models/__init__ 注册（Alembic metadata 完整性）。"""

    def test_previously_unregistered_models_importable(self):
        """此前遗漏的 5 个模型可从 app.models 导入."""
        from app.models import (
            DataSourceMetric,
            GraphWriteOutbox,
            MatchResult,
            ReviewAuditLog,
            ReviewQueue,
        )

        for model in (
            DataSourceMetric,
            GraphWriteOutbox,
            MatchResult,
            ReviewAuditLog,
            ReviewQueue,
        ):
            assert issubclass(model, Base)

    def test_metadata_covers_all_tablenames(self):
        """Base.metadata 覆盖全部 ORM 表（autogenerate 前提）."""
        expected = {
            "data_source_metrics",
            "graph_write_outbox",
            "match_results",
            "review_audit_log",
            "review_queue",
        }
        assert expected <= set(Base.metadata.tables.keys())

    def test_data_source_record_maps_last_successful_crawl_at(self):
        """迁移 024 新增列必须映射到 ORM（health_monitor hasattr 守卫依赖）."""
        from app.models import DataSourceRecord

        assert "last_successful_crawl_at" in DataSourceRecord.__table__.columns
