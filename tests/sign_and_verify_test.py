
import subprocess
import os
import sys
import shutil


class TestSignVerify(object):
    def _run_verification_script_and_check(self, image, cert_file_path, success_str, expected_value=0):
        res = subprocess.run(['sh', self._verification_script, image, cert_file_path])
        assert res.returncode == expected_value
        print(success_str)

    def test_basic_signature_verification(self):
        self._run_verification_script_and_check(os.path.join(self._out_dir_path, 'output_file.bin'),
                                                self._cert_file_path, "test case 1 - basic verify signature - SUCCESS")

    # change image size to something else - should fail on signature verification
    def test_modified_image_size(self):
        self._run_verification_script_and_check(os.path.join(self._out_dir_path, 'test_image_1.bin'),
                                                self._cert_file_path, "test case 2 - modified image size - SUCCESS", 1)

    def test_modified_image_sha1(self):
        self._run_verification_script_and_check(os.path.join(self._out_dir_path, 'test_image_2.bin'),
                                                self._cert_file_path, "test case 3 - modified image sha1 - SUCCESS", 1)

    def test_modified_image_data(self):
        self._run_verification_script_and_check(os.path.join(self._out_dir_path, 'test_image_3.bin'),
                                                self._cert_file_path, "test case 4 - modified image data - SUCCESS", 1)

    def test_modified_image_signature(self):
        self._run_verification_script_and_check(os.path.join(self._out_dir_path, 'test_image_4.bin'),
                                                self._cert_file_path, "test case 5 - modified image data - SUCCESS", 1)

    def test_verify_image_with_wrong_certificate(self):
        self._run_verification_script_and_check(os.path.join(self._out_dir_path, 'output_file.bin'),
                                                self._alt_cert_path, "test case 6 - verify with wrong signature - SUCCESS", 1)

    def __init__(self):
        self._test_path = os.path.dirname(os.path.abspath(__file__))
        self._modules_path = os.path.dirname(self._test_path)
        self._repo_path = os.path.join(self._modules_path, '../..')
        self._test_scripts_path = os.path.join(self._test_path, "scripts")
        sys.path.insert(0, self._test_path)
        sys.path.insert(0, self._modules_path)
        sys.path.insert(0, self._test_scripts_path)
        script_path = os.path.join(self._test_scripts_path, 'create_sign_and_verify_test_files.sh')
        self._verification_script = os.path.join(self._test_scripts_path, 'verify_image_sign_test.sh')
        self._out_dir_path = '/tmp/sign_verify_test'
        self._cert_file_path = os.path.join(self._out_dir_path, 'self_certificate.pem')
        self._alt_cert_path = os.path.join(self._out_dir_path, 'alt_self_certificate.pem')
        create_files_result = subprocess.run(['sh', script_path, self._repo_path, self._out_dir_path,
                                              self._cert_file_path,
                                              self._alt_cert_path])
        print(create_files_result)
        assert create_files_result.returncode == 0

    def __del__(self):
        shutil.rmtree(self._out_dir_path)


if __name__ == '__main__':
    t = TestSignVerify()
    t.test_basic_signature_verification()
    subprocess.run(['ls', '/tmp/sign_verify_test'])
    t.test_modified_image_data()
    t.test_modified_image_sha1()
    t.test_modified_image_signature()
    t.test_modified_image_size()
    t.test_verify_image_with_wrong_certificate()
