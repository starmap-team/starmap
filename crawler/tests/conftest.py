"""Pytest configuration for crawler tests."""
import sys
from unittest.mock import MagicMock

# Mock database dependencies before any crawler modules are imported
# This allows tests to run without psycopg/PostgreSQL
if "crawler.persistence.database" not in sys.modules:
    mock_db = MagicMock()
    mock_db.engine = MagicMock()
    mock_db.SessionLocal = MagicMock()
    mock_db.get_jd_raw_session = MagicMock()
    mock_db.get_compliance_session = MagicMock()
    sys.modules["crawler.persistence.database"] = mock_db

# Mock models module to avoid database connection
if "crawler.persistence.models" not in sys.modules:
    mock_models = MagicMock()
    # Create mock classes that the code expects
    mock_models.JdRaw = MagicMock()
    mock_models.JdStatus = MagicMock()
    mock_models.ComplianceLog = MagicMock()
    mock_models.Base = MagicMock()
    sys.modules["crawler.persistence.models"] = mock_models

if "crawler.persistence" not in sys.modules:
    # Import the real persistence module but with mocked database
    import crawler.persistence
    # Add mocked submodules to it
    crawler.persistence.dao = MagicMock()
    crawler.persistence.models = sys.modules["crawler.persistence.models"]
    crawler.persistence.database = sys.modules["crawler.persistence.database"]

# Mock scrapy and spider modules for run_incremental tests
if "scrapy" not in sys.modules:
    sys.modules["scrapy"] = MagicMock()
    sys.modules["scrapy.crawler"] = MagicMock()
    sys.modules["scrapy.signals"] = MagicMock()

if "crawler.spiders" not in sys.modules:
    sys.modules["crawler.spiders"] = MagicMock()
    sys.modules["crawler.spiders.boss"] = MagicMock()
    sys.modules["crawler.spiders.lagou"] = MagicMock()
    sys.modules["crawler.spiders.job51"] = MagicMock()
