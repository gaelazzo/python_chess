import datetime
import os
import json
import re
from typing import Any, Dict, TypeVar

# Regex for ISO 8601 formats (supports with and without milliseconds)
ISO_8601_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[\+\-]\d{2}:\d{2})?$"
)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()  # Convert datetime to ISO 8601 string
        return super().default(obj)

# Custom decoder
def custom_json_decoder(d: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in d.items():
        if isinstance(value, str) and ISO_8601_REGEX.match(value):
            try:
                # Try to convert ISO 8601 strings to datetime
                d[key] = datetime.datetime.fromisoformat(value)
            except ValueError:
                pass  # Not a date, leave the value as is
    return d


def read_struct(filename:str):
    if os.stat(filename).st_size == 0:
        raise ValueError(f"The file {filename} is empty.")
    
    try:
        with open(filename, "r", encoding="utf8") as data_file:
            return json.load(data_file, object_hook=custom_json_decoder)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to decode JSON from {filename}: {e}")
    
    
    

def write_struct(filename:str, struct):
    with open(filename, "w", encoding="utf8") as data_file:
        json.dump(struct, data_file, indent=4, cls=CustomJSONEncoder, ensure_ascii=False)



    