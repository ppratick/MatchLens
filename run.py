"""Source-tree launcher; avoids editable .pth quirks in hidden/iCloud environments."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from matchlens.cli import main

if __name__ == "__main__":
    main()
