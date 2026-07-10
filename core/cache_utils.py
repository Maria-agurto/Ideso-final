"""
Helpers de caché / logging — puerto directo de la celda 6 del notebook.

- cache_get_or_compute_mongo: caché persistente en Mongo (para svc/rnns/lstm,
  igual que antes — sobrevive a un refresh del navegador o un redeploy).
- cache_get_or_compute_local: caché barata en memoria del proceso de
  Streamlit (para salud/mercado/portafolio), usando st.cache_data por
  debajo en vez de un dict + threading.Lock manual.
- log_resultado: guarda cada resultado en logs_resultados, igual que el
  notebook (auditoría/histórico, no es el caché).
"""
import time
from datetime import datetime, timezone

from core.db import get_collections


def cache_get_or_compute_mongo(key: str, ttl_segundos: int, compute_fn):
    col_usuarios, col_cache, col_logs = get_collections()
    doc = col_cache.find_one({"key": key})
    if doc and (time.time() - doc["ts"]) < ttl_segundos:
        return doc["value"]

    value = compute_fn()
    col_cache.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value, "ts": time.time()}},
        upsert=True,
    )
    return value


def log_resultado(modulo: str, key: str, payload: dict) -> None:
    try:
        _, _, col_logs = get_collections()
        col_logs.insert_one(
            {
                "modulo": modulo,
                "key": key,
                "payload": payload,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:  # noqa: BLE001
        # Un fallo de logging nunca debe tumbar la respuesta al usuario
        print(f"[log_resultado] no se pudo guardar log de '{modulo}:{key}': {e}")
