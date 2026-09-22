#!/usr/bin/env python3
import json
import csv
from datetime import datetime
from pathlib import Path

# Directorios (CORREGIDO: apunta a task_events)
TASKS_DIR = Path("task_events")
CSV_FILE = Path("data/tasks.csv")


def get_duration_minutes(start_time, end_time):
    """Calcula la duración en minutos entre dos timestamps ISO."""
    if not start_time or not end_time:
        return None
    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        return int((end - start).total_seconds() / 60)
    except (ValueError, TypeError):
        return None


def parse_timestamp(value):
    """Convierte string ISO a datetime, o None si falla."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def process_tasks():
    """Procesa los JSON de task_events y consolida en CSV."""
    if not TASKS_DIR.exists():
        print(f"ℹ️  No existe la carpeta {TASKS_DIR}")
        return

    # Agrupar eventos por task_name
    events = {}

    for json_file in sorted(TASKS_DIR.glob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️  Error leyendo {json_file}")
            continue
        except Exception as e:
            print(f"⚠️  Error con {json_file}: {e}")
            continue

        name = data.get("task_name")
        if not name:
            continue

        status = (data.get("status") or "").lower()
        events.setdefault(name, {})[status] = data

    # Construir filas
    tasks = []
    for name, ev in events.items():
        start_ev = ev.get("started", {})
        end_ev = ev.get("finished") or ev.get("ended") or ev.get("stopped") or {}

        start_time = start_ev.get("start_time")
        end_time = end_ev.get("end_time")

        # Fallback: si el evento único trae ambos campos
        if not start_time and not end_time:
            # Puede ser un único JSON con start_time y end_time
            single = next(iter(ev.values()), {})
            start_time = single.get("start_time")
            end_time = single.get("end_time")

        duration = get_duration_minutes(start_time, end_time)

        tasks.append({
            "fecha": (start_time or "").split("T")[0],
            "tarea": name,
            "hora_inicio": start_time or "",
            "hora_termino": end_time or "",
            "duracion_minutos": duration if duration is not None else "",
            "categoria": start_ev.get("category") or end_ev.get("category", ""),
            "notas": (start_ev.get("notes") or end_ev.get("notes") or "").strip(),
        })

    if not tasks:
        print("ℹ️  No hay tareas para procesar")
        return

    # Ordenar por hora de inicio
    tasks.sort(key=lambda t: t["hora_inicio"] or "")

    CSV_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ['fecha', 'tarea', 'hora_inicio', 'hora_termino',
                  'duracion_minutos', 'categoria', 'notas']

    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tasks)

    print(f"✅ {len(tasks)} tareas procesadas y guardadas en {CSV_FILE}")


if __name__ == "__main__":
    process_tasks()
