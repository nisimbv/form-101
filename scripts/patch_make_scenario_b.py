"""
Patch Scenario B Router — adds validatePdf error fallback.

When validatePdf returns {success:false} (timeout / API error),
Route A still runs (WhatsApp + confirmSubmission) instead of silently failing.

Usage:
    $env:MAKE_API_TOKEN="<your-token>"; python -m scripts.patch_make_scenario_b

Requirements:
    - MAKE_API_TOKEN environment variable set
    - Scenario B must already exist (id=4664175)
"""
import os, sys, json
import requests

TOKEN    = os.environ.get('MAKE_API_TOKEN', '')
BASE     = 'https://eu1.make.com/api/v2'
SCENARIO = 4664175


def main() -> None:
    if not TOKEN:
        print('❌  MAKE_API_TOKEN not set')
        print('    Set it first:  $env:MAKE_API_TOKEN="<token>"')
        sys.exit(1)

    headers = {'Authorization': f'Token {TOKEN}', 'Content-Type': 'application/json'}

    # 1. Fetch current blueprint
    print(f'Fetching blueprint for scenario {SCENARIO}...')
    r = requests.get(f'{BASE}/scenarios/{SCENARIO}/blueprint', headers=headers, timeout=15)
    if r.status_code != 200:
        print(f'❌  GET failed: {r.status_code} {r.text[:200]}')
        sys.exit(1)

    blueprint = r.json()['response']['blueprint']

    # 2. Locate the Router module and update Route A filter
    patched = False
    for module in blueprint.get('flow', []):
        if module.get('module') != 'builtin:BasicRouter':
            continue
        for route in module.get('routes', []):
            flow = route.get('flow', [])
            if not flow:
                continue
            first = flow[0]
            f = first.get('filter', {})
            conditions = f.get('conditions', [])
            # Route A already has passed/skipped conditions — check if error fallback missing
            has_pass    = any(c[0].get('a','') == '{{2.data.passed}}'  and c[0].get('b') == 'true'  for c in conditions if c)
            has_skip    = any(c[0].get('a','') == '{{2.data.skipped}}' and c[0].get('b') == 'true'  for c in conditions if c)
            has_error   = any(c[0].get('a','') == '{{2.data.success}}' and c[0].get('b') == 'false' for c in conditions if c)
            if has_pass and has_skip and not has_error:
                conditions.append([{'a': '{{2.data.success}}', 'b': 'false', 'o': 'text:equal'}])
                f['conditions'] = conditions
                f['name'] = 'QA passed, skipped, or error'
                first['filter'] = f
                patched = True
                print('  ✓ Added error fallback to Route A filter')
                break
        if patched:
            break

    if not patched:
        print('  ⏭  Fallback condition already present or Router not found — nothing to do')
        sys.exit(0)

    # 3. PATCH the scenario
    body = json.dumps({
        'blueprint':  json.dumps(blueprint),
        'scheduling': json.dumps({'type': 'immediately'}),
    })
    r2 = requests.patch(f'{BASE}/scenarios/{SCENARIO}', headers=headers, data=body, timeout=20)
    if r2.status_code == 200:
        s = r2.json().get('scenario', {})
        print(f'✅  Scenario B updated — isActive={s.get("isActive")}  invalid={s.get("isinvalid")}')
    else:
        print(f'❌  PATCH failed: {r2.status_code}')
        print(r2.text[:400])
        sys.exit(1)


if __name__ == '__main__':
    main()
