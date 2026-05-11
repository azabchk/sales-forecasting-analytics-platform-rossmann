import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("MODEL_PATH", "ml/artifacts/model.joblib")
os.environ.setdefault("MODEL_METADATA_PATH", "ml/artifacts/model_metadata.json")
os.environ.setdefault("BACKEND_HOST", "0.0.0.0")
os.environ.setdefault("BACKEND_PORT", "8000")
os.environ.setdefault("PREFLIGHT_ALERTS_SCHEDULER_ENABLED", "0")

# Override JWT auth for all unit/integration tests so routes are reachable
# without a real database user or signed token.
from app.main import app  # noqa: E402  (must come after env setup)
from app.security.jwt import get_current_user  # noqa: E402

_TEST_USER = {
    "id": 1,
    "email": "test@example.com",
    "username": "testuser",
    "role": "admin",
    "is_active": True,
}
app.dependency_overrides[get_current_user] = lambda: _TEST_USER
