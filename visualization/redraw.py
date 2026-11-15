"""Redraw the five research figures using the published data tables."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from extension_plots import main

if __name__ == "__main__":
    main(public=True)
