import pytest

from app.services.judge_service import evaluate_batch_async, evaluate_sample_async


@pytest.mark.asyncio
async def test_evaluate_sample_async_returns_perfect_overlap():
    golden = {
        'id': 'golden-1',
        'required_skills': [
            {'name': 'Python'},
            {'name': 'SQL'},
        ],
        'bonus_skills': [
            {'name': 'Docker'},
        ],
    }
    system = {
        'id': 'system-1',
        'required_skills': [
            {'name': 'Python'},
            {'name': 'SQL'},
        ],
        'bonus_skills': [
            {'name': 'Docker'},
        ],
    }

    result = await evaluate_sample_async(golden, system)

    assert result.sample_id == 'golden-1'
    assert result.precision == pytest.approx(1.0, rel=1e-6)
    assert result.recall == pytest.approx(1.0, rel=1e-6)
    assert result.f1 == pytest.approx(1.0, rel=1e-6)


@pytest.mark.asyncio
async def test_evaluate_sample_async_penalizes_partial_overlap():
    golden = {
        'id': 'golden-2',
        'required_skills': [
            {'name': 'Python'},
            {'name': 'SQL'},
            {'name': 'Docker'},
        ],
        'bonus_skills': [],
    }
    system = {
        'id': 'system-2',
        'required_skills': [
            {'name': 'Python'},
            {'name': 'Kubernetes'},
        ],
        'bonus_skills': [],
    }

    result = await evaluate_sample_async(golden, system)

    assert 0.0 < result.precision < 1.0
    assert 0.0 < result.recall < 1.0
    assert 0.0 < result.f1 < 1.0
    assert result.precision > result.f1


@pytest.mark.asyncio
async def test_evaluate_batch_async_aggregates_metrics(tmp_path):
    golden_file = tmp_path / 'golden.jsonl'
    system_file = tmp_path / 'system.jsonl'

    golden_file.write_text(
        '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
        '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[{"name":"Docker"}]}\n',
        encoding='utf-8',
    )
    system_file.write_text(
        '{"id":"g1","required_skills":[{"name":"Python"}],"bonus_skills":[]}\n'
        '{"id":"g2","required_skills":[{"name":"SQL"}],"bonus_skills":[{"name":"Docker"}]}\n',
        encoding='utf-8',
    )

    metrics = await evaluate_batch_async(golden_file, system_file, threshold=0.9)

    assert metrics.total_samples == 2
    assert metrics.evaluated_samples == 2
    assert metrics.avg_precision == pytest.approx(1.0, rel=1e-6)
    assert metrics.avg_recall == pytest.approx(1.0, rel=1e-6)
    assert metrics.avg_f1 == pytest.approx(1.0, rel=1e-6)
    assert metrics.quality_gate['passed'] is True
