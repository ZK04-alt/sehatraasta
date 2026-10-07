"""AUTOMATED high-confidence, redacted tracked-file/history secret scan.

This small scanner does not claim full entropy or credential-provider coverage.
It reads Git blobs, never prints matched secret values, and scans each blob once.
"""
import json
from pathlib import Path
import re
import subprocess

PATTERNS = {
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b',
    'aws_access_id': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'google_api_key': rb'\bAIza[0-9A-Za-z_-]{35}\b',
    'slack_token': rb'\bxox[baprs]-[0-9A-Za-z-]{20,}\b',
    'openai_key': rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}\b',
}


def main():
    objects = subprocess.check_output(['git', 'rev-list', '--all', '--objects']).decode().splitlines()
    blobs = {}
    process = subprocess.Popen(['git', 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    findings, checked = [], 0
    try:
        for record in objects:
            identifier, _, name = record.partition(' ')
            process.stdin.write(identifier.encode() + b'\n')
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            if len(header) != 3:
                raise RuntimeError('Incomplete Git object read')
            data = process.stdout.read(int(header[2]))
            if len(data) != int(header[2]) or process.stdout.read(1) != b'\n':
                raise RuntimeError('Incomplete Git object content')
            if header[1] != 'blob':
                continue
            checked += 1
            for kind, expression in PATTERNS.items():
                for match in re.finditer(expression, data):
                    findings.append({'git_blob':identifier, 'path':name,
                                     'line':data[:match.start()].count(b'\n')+1, 'detector':kind})
    finally:
        process.stdin.close()
        process.wait()
    result = {'evidence_class':'AUTOMATED', 'source_head':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
              'method':'All reachable Git objects; unique blobs; high-confidence signatures; redacted matches',
              'unique_blobs_checked':checked, 'findings':findings,
              'limitations':'No entropy scan, provider validation, ignored/untracked files or inaccessible remote history. No secret values emitted.'}
    output = Path('tmp/final-secret-scan.json')
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'evidence_class':'AUTOMATED', 'unique_blobs_checked':checked,
                      'findings':len(findings), 'report':str(output)}))


if __name__ == '__main__':
    main()
