import json
import fnmatch
import base64


class RedisMock():

    def __init__(self, host="None", port=0, db=0):
        return

    def load_file(self, file_name):
        with open(file_name) as fp:
            try:
                self.data = json.load(fp)
            except json.JSONDecodeError:
                print("Json decode error")
        self.data = self.encode_data(self.data)

    def encode_data(self, json_data):
        new_data = {}
        for key, value in json_data.items():
            new_value = {}
            for pb, bin_data in value.items():
                bin_pb = pb.encode()
                new_value[bin_pb] = base64.b64decode(bin_data.encode())
            new_data[key] = new_value
        return new_data

    def hgetall(self, key):
        return self.data[key]

    def keys(self, match):
        kp = match.replace("[^", "[!")
        kys = fnmatch.filter(self.data.keys(), kp)
        return [ky.encode() for ky in kys]
