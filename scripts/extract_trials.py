"""Generate from public or explicitly synthetic sources; never accepts patient data."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rematch.client import request

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', help='NCT ID or SYN-LOW / SYN-HIGH / SYN-UNKNOWN / SYN-REMATCH')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    request('team-1', 'POST', '/team/sources/' + args.source)
    print(request('team-1', 'POST', '/team/listings', {'source_id': args.source, 'mode': 'live' if args.live else 'offline'}))
