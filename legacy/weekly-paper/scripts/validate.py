"""Run all original and Rev12 tests with a workspace-safe temporary directory."""
from pathlib import Path
import sys, tempfile, unittest, json, time, importlib.metadata
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
temp_root=ROOT/'.runtime'/'test_tmp'
temp_root.mkdir(parents=True,exist_ok=True)
tempfile.tempdir=str(temp_root)
started=time.time()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
versions={}
for name in ('numpy','pandas','openpyxl','reportlab','Pillow','matplotlib','tzdata'):
    try:versions[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:versions[name]='metadata unavailable'
record={'command':'python scripts/validate.py','python':sys.version.split()[0],
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'passed':result.wasSuccessful(),'elapsed_seconds':round(time.time()-started,3),
        'dependency_versions':versions,'temporary_directory':'workspace .runtime/test_tmp',
        'note':'Software behavior checks, not evidence of trading profitability.'}
destination=ROOT/'results'/'rev12_validation'
destination.mkdir(parents=True,exist_ok=True)
(destination/'Test_Result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
sys.exit(not result.wasSuccessful())
