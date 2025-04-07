import datetime
import os
import json
import re
from typing import Any, Dict, TypeVar

# Regex per formati ISO 8601 (supporta con e senza millisecondi)
ISO_8601_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[\+\-]\d{2}:\d{2})?$"
)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()  # Converte datetime in stringa ISO 8601
        return super().default(obj)

# Decoder personalizzato
def custom_json_decoder(d: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in d.items():
        if isinstance(value, str) and ISO_8601_REGEX.match(value):
            try:
                # Prova a convertire stringhe ISO 8601 in datetime
                d[key] = datetime.datetime.fromisoformat(value)
            except ValueError:
                pass  # Non è una data, lascia il valore com'è
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



    