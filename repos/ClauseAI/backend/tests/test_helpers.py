import json

def read_json(path: str):
    with open(path, "r") as file:
        return json.load(file)