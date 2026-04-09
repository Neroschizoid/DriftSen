from pydantic import BaseModel
from typing import Dict, Any, List, Union

class InferenceRequest(BaseModel):
    features: Union[Dict[str, Any], List[float]]
