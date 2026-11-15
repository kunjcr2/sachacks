"""Check the React browser session contracts against a running local backend."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from rematch.common.config import API_URL

def run_once():
    with httpx.Client(base_url=API_URL, trust_env=False, timeout=20, headers={'X-Rematch-Intent': 'browser'}) as client:
        def call(method, path, body=None):
            response = client.request(method, '/api' + path, json=body)
            response.raise_for_status()
            return response.json()
        call('POST', '/demo/session', {'actor': 'team-1'})
        for study in ['SYN-LOW', 'SYN-HIGH', 'SYN-UNKNOWN']:
            call('POST', '/team/listings', {'source_id': study, 'mode': 'offline'})
        call('POST', '/demo/session', {'actor': 'onboarding'})
        created = call('POST', '/profiles', dict(name='React Demo Check', contact_method='email', contact='react-check@example.invalid', assigned_pcp='doctor-1'))
        pid = created['patient_id']
        assert 'demo_token' not in created
        for kind in ['screening', 'records']:
            call('POST', '/me/permissions', {'kind': kind, 'granted': True})
        call('POST', '/me/records/connect')
        assert call('GET', '/me/clinical-summary')['current']
        preview = call('POST', '/me/studies/SYN-LOW:team-1/preview')
        introduction = call('POST', '/me/introductions', {'preview_id': preview['id'], 'confirmed': True})
        call('POST', '/demo/session', {'actor': 'doctor-1'})
        queue = call('GET', '/doctor/discussions')
        own = [row for row in queue if row['patient_id'] == pid]
        assert {row['listing_id'] for row in own} == {'SYN-HIGH:team-1', 'SYN-UNKNOWN:team-1'}
        call('POST', '/doctor/discussions/' + pid + '|SYN-HIGH:team-1', {'outcome': 'COMPLETED', 'note': 'Synthetic demonstration discussion.'})
        call('POST', '/demo/session', {'actor': pid})
        high = call('POST', '/me/studies/SYN-HIGH:team-1/preview')
        call('POST', '/me/introductions', {'preview_id': high['id'], 'confirmed': True})
        call('POST', '/me/records/followup')
        assert any(fact['field'] == 'hba1c' and fact['value'] == 9.1 for fact in call('GET', '/me/clinical-summary')['current'])
        call('POST', '/demo/session', {'actor': 'team-1'})
        assert next(row for row in call('GET', '/team/introductions') if row['id'] == introduction['id'])['approved_packet'] == preview['exact_packet']
        call('POST', '/demo/session', {'actor': 'team-2'})
        assert not any(row['id'] == introduction['id'] for row in call('GET', '/team/introductions'))
        call('POST', '/demo/session', {'actor': pid})
        call('DELETE', '/me/records')
        assert call('GET', '/me')['patient']['deleted']
    print('Browser API journey passed: onboarding, records, both routes, exact disclosure, role isolation, reassessment and deletion.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeat', type=int, default=1)
    args = parser.parse_args()
    for _ in range(args.repeat):
        run_once()
