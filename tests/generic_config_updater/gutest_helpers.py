import json
import jsonpatch
import os
import shutil
import sys
import unittest
from unittest.mock import MagicMock, Mock, call

class MockSideEffectDict:
    def __init__(self, map):
        self.map = map

    def side_effect_func(self, *args, **kwargs):
        l = [str(arg) for arg in args]
        key = tuple(l)
        value = self.map.get(key)
        if value is None:
            raise ValueError(f"Given arguments were not found in arguments map.\n  Arguments: {key}\n  Map: {self.map}")

        return value

def create_side_effect_dict(map):
    return MockSideEffectDict(map).side_effect_func

class FilesLoader:
    def __init__(self):
        self.files_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files")
        self.cache = {}

    def __getattr__(self, attr):
        return self._load(attr)

    def _load(self, file_name):
        normalized_file_name = file_name.lower()

        # Try load json file
        json_file_path = os.path.join(self.files_path, f"{normalized_file_name}.json")
        if os.path.isfile(json_file_path):
            with open(json_file_path) as fh:
                text = fh.read()
                return json.loads(text)

        # Try load json-patch file
        jsonpatch_file_path = os.path.join(self.files_path, f"{normalized_file_name}.json-patch")
        if os.path.isfile(jsonpatch_file_path):
            with open(jsonpatch_file_path) as fh:
                text = fh.read()
                return jsonpatch.JsonPatch(json.loads(text))

        raise ValueError(f"There is no file called '{file_name}' in 'files/' directory")

# Files.File_Name will look for a file called "file_name" in the "files/" directory
Files = FilesLoader()
