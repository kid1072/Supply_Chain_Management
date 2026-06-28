import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.example_data_service import generate_example_data, load_example_data


def ensure_example_data_files() -> None:
    example_dir = get_settings().example_dir_path
    if not example_dir.exists() or not list(example_dir.glob("*.json")):
        generate_example_data()


if __name__ == "__main__":
    ensure_example_data_files()
    session = SessionLocal()
    try:
        result = load_example_data(session)
        session.commit()
        print(result)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
