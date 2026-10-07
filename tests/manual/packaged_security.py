"""Retain the raw audit and assess only hash-bound, evidenced code absence.

No ignored advisories. Unknown findings, changed bootstrap or introduced
setuptools implementation fail. The audit's original exit status is preserved.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
from inspect_android_package import inspect,main as inventory_main

BOOTSTRAP='fd7c9fad11d6b7d1a308901d0e2c89e32fb7ade5b7672ab33ed8f9a846617613'
KNOWN={
 'CVE-2025-47273':{'CVE-2025-47273','PYSEC-2025-49','GHSA-5rjg-fvgr-3xxf'},
 'CVE-2024-6345':{'CVE-2024-6345','PYSEC-2026-1918','GHSA-cx63-2mw6-8hw5'},
 'CVE-2026-59890':{'CVE-2026-59890','PYSEC-2026-3447','GHSA-h35f-9h28-mq5c'},
}


def assess(inventory,audit,raw_exit):
    statements,unresolved=[],[]
    code_absent = inventory.get('bootstrap_sha256')==BOOTSTRAP and not any(
        '/setuptools/' in name or '!setuptools/' in name for name in inventory['packaged_files'])
    for package in audit['dependencies']:
        for finding in package['vulns']:
            aliases={finding['id'],*finding.get('aliases',[])}
            known=next((key for key,ids in KNOWN.items() if aliases&ids),None)
            if package['name'].lower()=='setuptools' and package['version']=='68.2.2' and known and code_absent:
                if known not in statements: statements.append(known)
            else: unresolved.append({'package':package['name'],'version':package['version'],'advisory':finding['id']})
    valid=raw_exit in (0,1) and not unresolved and (raw_exit==0 or bool(statements))
    return {'raw_audit_exit':raw_exit,'code_absent':code_absent,'evidence_disposition':'CLEAR_FOR_KNOWN_FINDINGS' if valid else 'FAIL',
        'artifact_sha256':inventory['sha256'],'vex_advisories':statements,'unresolved':unresolved}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('artifact',type=Path);parser.add_argument('folder',type=Path)
    args=parser.parse_args();args.folder.mkdir(parents=True,exist_ok=True)
    inventory_path=args.folder/'inventory.json'
    subprocess.run([sys.executable,str(Path(__file__).with_name('inspect_android_package.py')),str(args.artifact),str(inventory_path)],check=True)
    raw=args.folder/'raw-audit.json'
    with (args.folder/'raw-audit.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,'-m','pip_audit','-r',str(inventory_path.with_suffix('.requirements.txt')),
            '--no-deps','--disable-pip','--format','json','--output',str(raw)],stdout=log,stderr=subprocess.STDOUT)
    inventory=json.loads(inventory_path.read_text());audit=json.loads(raw.read_text())
    disposition=assess(inventory,audit,result.returncode)
    if inventory['pillow_related_files'] or inventory['native_failures']:
        disposition['evidence_disposition']='FAIL'
    (args.folder/'disposition.json').write_text(json.dumps(disposition,indent=2)+'\n')
    vex={'@context':'https://openvex.dev/ns/v0.2.0','@id':'urn:sha256:'+inventory['sha256'],
        'author':'SehatRaasta automated artifact review; independent security review unverified',
        'timestamp':datetime.now(timezone.utc).isoformat(),'version':1,'statements':[
            {'vulnerability':{'name':advisory},'products':[{'@id':'urn:sha256:'+inventory['sha256']}],
            'status':'not_affected','justification':'vulnerable_code_not_present',
            'impact_statement':'Exact known Chaquopy bootstrap hash; metadata/pkg_resources retained; full setuptools implementation absent across nested archives.'}
            for advisory in disposition['vex_advisories']]}
    (args.folder/'vex.json').write_text(json.dumps(vex,indent=2)+'\n')
    print(json.dumps(disposition,indent=2))
    return 0 if disposition['evidence_disposition']=='CLEAR_FOR_KNOWN_FINDINGS' else 1

if __name__=='__main__':sys.exit(main())
