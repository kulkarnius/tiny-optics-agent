import sys
from pathlib import Path

# Add project root to sys.path so absolute imports work (e.g. `from rag.chunker import ...`)
sys.path.insert(0, str(Path(__file__).parent.parent))
