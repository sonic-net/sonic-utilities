import sys,zipfile,hashlib
with zipfile.ZipFile(sys.argv[1]) as full, zipfile.ZipFile(sys.argv[2]) as runtime:
    original=set(full.namelist());actual=set(runtime.namelist())
    removed={p for p in original if p.startswith("tests/")}
    assert removed, "negative control: original wheel must really contain tests"
    assert original-removed==actual,(sorted(original-removed-actual),sorted(actual-original))
    for name in actual:
        if not name.endswith(".dist-info/RECORD"):
            assert full.read(name)==runtime.read(name),name
        assert full.getinfo(name).external_attr == runtime.getinfo(name).external_attr, name
    print("Runtime-wheel-contract-PASS",len(actual),"files; excluded",len(removed),"developer-test files; all other bytes identical")
