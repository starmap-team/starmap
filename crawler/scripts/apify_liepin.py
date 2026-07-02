#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler.compliance import is_allowed, log_request
from crawler.dedup import hex64, simhash
from crawler.pipelines.clean import clean_html
from crawler.persistence import dao
from crawler.persistence.models import JdStatus

log = logging.getLogger(__name__)

_COMPLIANCE_UA = 'StarMap-Apify/1.0 (compliance-audit)'
LIEPIN_ACTOR = 'anchor/liepin-scraper'


def _extract_str(val, fallback: str = '') -> str:
    if val is None:
        return fallback
    if isinstance(val, dict):
        return val.get('name', val.get('title', str(val)))
    return str(val)


def run_apify_liepin(
    max_items: int = 50,
    keywords: list[str] | None = None,
    dry_run: bool = False,
    force_paid: bool = False,
) -> dict:
    from apify_client import ApifyClient

    token = os.getenv('APIFY_TOKEN')
    if not token:
        log.error('APIFY_TOKEN not set')
        return {'total': 0, 'inserted': 0, 'failed': 0, 'error': 'missing APIFY_TOKEN'}

    if not force_paid:
        log.warning('liepin-scraper is PAY_PER_EVENT (paid). Use --force-paid to run.')
        return {'total': 0, 'inserted': 0, 'failed': 0, 'error': 'paid_actor_skipped'}

    keywords = keywords or ['python', 'java', '算法', '前端', '大模型']
    log.info('Calling Actor: %s | keywords=%s | max=%d', LIEPIN_ACTOR, keywords, max_items)

    client = ApifyClient(token)
    run_input = {'keywords': keywords, 'maxResults': max_items}

    try:
        run = client.actor(LIEPIN_ACTOR).call(run_input=run_input)
    except Exception as e:
        log.error('Actor call failed: %s', e)
        return {'total': 0, 'inserted': 0, 'failed': 0, 'error': str(e)}

    status = run.status if hasattr(run, 'status') else run.get('status', '')
    if status != 'SUCCEEDED':
        return {'total': 0, 'inserted': 0, 'failed': 0, 'error': f'Actor status: {status}'}

    dataset_id = run.default_dataset_id if hasattr(run, 'default_dataset_id') else run['defaultDatasetId']
    items = list(client.dataset(dataset_id).iterate_items())
    log.info('Apify returned %d items', len(items))

    log_request(source_site='liepin', target_url=f'apify://actor/{LIEPIN_ACTOR}/dataset/{dataset_id}',
                robots_allowed=True, user_agent=_COMPLIANCE_UA, qps=0.0, response_code=200,
                response_bytes=len(json.dumps(items, ensure_ascii=False).encode()))

    if dry_run:
        for item in items[:3]:
            log.info(json.dumps(item, ensure_ascii=False, indent=2)[:500])
        return {'total': len(items), 'inserted': 0, 'failed': 0, 'skipped': 0}

    inserted = failed = skipped = 0
    for item in items:
        try:
            title = _extract_str(item.get('jobTitle') or item.get('title') or item.get('job_name'))
            company = _extract_str(item.get('company') or item.get('companyName') or item.get('company_name'))
            description = item.get('description') or item.get('jobDesc') or item.get('job_description') or ''
            salary = item.get('salary') or item.get('salaryDesc') or ''
            location = _extract_str(item.get('location') or item.get('city') or item.get('workCity'))
            url = item.get('jobUrl') or item.get('url') or item.get('link') or ''
            education = _extract_str(item.get('education') or item.get('eduLevel'))
            work_year = item.get('workYear') or item.get('experience') or ''
            item_id = item.get('id') or item.get('itemId') or item.get('positionId') or ''

            if not title and not description:
                skipped += 1; continue

            if not url or not url.strip():
                url = f'apify://liepin/{dataset_id}/{item_id}' if item_id else f'apify://liepin/{dataset_id}/title/{hash(title) % 10**8}'

            robots_ok = is_allowed(url, _COMPLIANCE_UA)
            log_request(source_site='liepin', target_url=url, robots_allowed=robots_ok,
                        user_agent=_COMPLIANCE_UA, qps=0.0, response_code=200,
                        response_bytes=len(description.encode()) if description else 0)

            clean = clean_html(description) if description else ''
            if not clean or len(clean) < 50:
                parts = [p for p in [title, company, education, str(work_year), salary] if p]
                clean = ' '.join(parts)
                if len(clean) < 30:
                    skipped += 1; continue

            salary_min = salary_max = None
            if isinstance(salary, dict):
                salary_min = salary.get('min'); salary_max = salary.get('max')
            elif salary:
                nums = re.findall(r'(\d+)', str(salary))
                if len(nums) >= 2:
                    salary_min = int(nums[0]) * 1000; salary_max = int(nums[1]) * 1000

            rec = {
                'source_site': 'liepin', 'source_url': url, 'raw_html': description,
                'clean_text': clean, 'job_title': title[:200], 'company': company or None,
                'salary_min': salary_min, 'salary_max': salary_max, 'location': location or None,
                'publish_date': date.today(), 'content_hash': hex64(simhash(clean)),
                'status': JdStatus.raw,
            }
            r = dao.upsert_jd(rec)
            if r == 'inserted': inserted += 1
            elif r == 'duplicate': skipped += 1
            else: failed += 1
        except Exception as e:
            log.warning('Item failed: %s', e); failed += 1

    summary = {'total': len(items), 'inserted': inserted, 'failed': failed, 'skipped': skipped}
    log.info('Liepin done: %s', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description='Apify Liepin crawler')
    parser.add_argument('--max', type=int, default=50)
    parser.add_argument('--keywords', nargs='+', default=['python', 'java', '算法', '前端', '大模型'])
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force-paid', action='store_true', help='Confirm paid actor')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    summary = run_apify_liepin(max_items=args.max, keywords=args.keywords, dry_run=args.dry_run, force_paid=args.force_paid)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
