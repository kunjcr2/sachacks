"""Import a changed local synthetic fixture for an authorized demo patient."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rematch.client import request

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--patient', default='patient-1')
    args = parser.parse_args()
    print(request(args.patient, 'POST', '/me/records/followup'))
