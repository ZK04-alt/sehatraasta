import importlib.util
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'manual'))
from packaged_security import assess,BOOTSTRAP


def test_known_code_absence_is_bound_to_bootstrap_and_no_new_findings():
    inventory={'sha256':'fictional','bootstrap_sha256':BOOTSTRAP,'packaged_files':['bootstrap.imy!pkg_resources/__init__.pyc','bootstrap.imy!setuptools-68.2.2.dist-info/METADATA']}
    audit={'dependencies':[{'name':'setuptools','version':'68.2.2','vulns':[{'id':'PYSEC-2025-49'}]}]}
    assert assess(inventory,audit,1)['evidence_disposition']=='CLEAR_FOR_KNOWN_FINDINGS'
    inventory['packaged_files'].append('requirements.imy!setuptools/package_index.pyc')
    assert assess(inventory,audit,1)['evidence_disposition']=='FAIL'
    inventory['packaged_files'].pop();inventory['bootstrap_sha256']='changed'
    assert assess(inventory,audit,1)['evidence_disposition']=='FAIL'
    inventory['bootstrap_sha256']=BOOTSTRAP
    audit['dependencies'][0]['vulns'].append({'id':'UNKNOWN-FUTURE-ADVISORY'})
    assert assess(inventory,audit,1)['evidence_disposition']=='FAIL'
