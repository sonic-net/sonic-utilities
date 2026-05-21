import os
import shutil
import tempfile

yang_models_path = '/usr/local/yang-models'

# Per-test temporary YANG directory to avoid modifying the global one
_temp_yang_dir = None


def setup_temp_yang_dir(test_path, test_name, test_yang_models):
    """Create a temporary YANG models directory with test models added.

    Copies the real /usr/local/yang-models to a temp directory, then
    overlays the test-specific YANG models on top.  Returns the temp
    directory path.  This avoids modifying the global YANG directory,
    which would race with parallel test workers that also read it.
    """
    global _temp_yang_dir
    _temp_yang_dir = tempfile.mkdtemp(prefix='yang-models-test-')
    # Copy all real YANG models
    for entry in os.listdir(yang_models_path):
        src = os.path.join(yang_models_path, entry)
        dst = os.path.join(_temp_yang_dir, entry)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
    # Overlay test-specific models
    for yang_model in test_yang_models:
        src = os.path.join(test_path, 'cli_autogen_input', test_name, yang_model)
        dst = os.path.join(_temp_yang_dir, yang_model)
        shutil.copy2(src, dst)
    return _temp_yang_dir


def cleanup_temp_yang_dir():
    """Remove the temporary YANG models directory."""
    global _temp_yang_dir
    if _temp_yang_dir and os.path.exists(_temp_yang_dir):
        shutil.rmtree(_temp_yang_dir, ignore_errors=True)
    _temp_yang_dir = None
