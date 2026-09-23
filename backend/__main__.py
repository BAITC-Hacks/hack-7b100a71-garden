"""Run with python -m backend after installing requirements.txt."""
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    uvicorn.run("backend.main:app", host=os.getenv("CAREER_QUEST_HOST", "127.0.0.1"),
                port=int(os.getenv("CAREER_QUEST_PORT", "8000")), workers=1)
