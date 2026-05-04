import numpy as np

def converter_numpy(obj):
    """Converte tipos numpy para tipos Python nativos."""
    if isinstance(obj, dict):
        return {k: converter_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [converter_numpy(v) for v in obj]
    elif isinstance(obj, (np.bool_)):
        return bool(obj)
    elif isinstance(obj, (np.integer)):
        return int(obj)
    elif isinstance(obj, (np.floating)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj
