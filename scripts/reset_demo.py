import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.generate_synthetic import initialize

if __name__ == '__main__':
    initialize(force=True)
    print('Central-v1 demo reset. Old clinic databases and keys were not modified.')
