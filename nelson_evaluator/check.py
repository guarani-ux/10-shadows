import importlib.util,json,os,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path.cwd()))
p=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location("adapter_under_test",p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
a=SimpleNamespace(verify_token=lambda:True,worker_id="constructed_authorized_test",requested_model=None)
os.environ["ANTIGRAVITY_CLI"]="nonexistent-bridge-fixture"
r=m.AntigravityBuilderProvider().execute(a,"Check unavailable bridge",Path.cwd(),[])
ok=r.exit_status=="FAILURE" and r.error_message=="CAPABILITY_PROVIDER_UNAVAILABLE"
print(json.dumps({"decision":"accept" if ok else "reject","reason":"An environment variable is not bridge execution; unavailable bridge must fail explicitly"}))
