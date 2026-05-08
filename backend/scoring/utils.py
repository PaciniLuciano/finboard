import numpy as np


def normalizar_dy(raw) -> float:
    """Converte dividendYield do yfinance para percentual %.
    yfinance retorna decimal (0.1326) para ativos EUA,
    mas às vezes retorna já em % (13.26) para ativos BR.
    Regra: se raw > 1 já é percentual; senão multiplica por 100.
    """
    if not raw:
        return 0.0
    v = float(raw)
    return round(v if v > 1 else v * 100, 2)


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
