"""Download inputs directly from their providers into external local storage."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
from zipfile import ZipFile

MANIFEST = Path(__file__).resolve().parents[1] / 'inputs.json'


def validate_payload(record, body):
    """Reject error pages and failed API responses before saving input bytes."""
    if record['role'].startswith('ili_') and record['path'].endswith('.json'):
        result = json.loads(body)
        if result.get('result') != 1 or not result.get('epidata'):
            raise ValueError('Provider returned no usable records: ' + record['path'])
    elif record['role'] == 'ili_table':
        fields = next(csv.reader(io.StringIO(body.decode('utf-8'))))
        if not {'time_value', 'issue_date', 'lag', 'value_raw', 'target_date'} <= set(fields):
            raise ValueError('Unexpected provider CSV header')
    else:
        with ZipFile(io.BytesIO(body)) as z:
            if 'xl/worksheets/sheet1.xml' not in z.namelist():
                raise ValueError('Unexpected provider workbook')


def fetch(record, output):
    """Fetch one manifest URL without replacing an existing local file."""
    target = output / record['path']
    if target.exists() or target.is_symlink():
        raise ValueError('Destination already exists: ' + str(target))
    request = urllib.request.Request(record['url'], headers={'User-Agent': 'Research-data-download/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    validate_payload(record, body)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(body)
    return {'path': record['path'], 'url': record['url'], 'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--path', help='download only this manifest path (small acquisition check)')
    args = parser.parse_args()
    records = json.loads(MANIFEST.read_text())['files']
    selected = [v for v in records if args.path is None or v['path'] == args.path]
    if not selected:
        parser.error('Unknown input path')
    try:
        for record in selected:
            print(json.dumps(fetch(record, args.output.resolve())), flush=True)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
