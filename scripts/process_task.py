#!/usr/bin/env python3

import json
import csv
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

TASKS_DIR = Path("task_events")
CSV_FILE = Path("data/tasks.csv")


# ============================================================
# FUNCIONES DE FECHA / HORA
# ============================================================

def parse_timestamp(value):
    """
    Convierte un timestamp ISO 8601 a datetime.

    Admite:
        2026-09-22T10:30:00
        2026-09-22T10:30:00Z
        2026-09-22T10:30:00-03:00
        2026-09-22T10:30:00+00:00
    """
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def get_duration_minutes(start_time, end_time):
    """
    Calcula duración en minutos entre dos timestamps.
    """
    start = parse_timestamp(start_time)
    end = parse_timestamp(end_time)

    if start is None or end is None:
        return None

    seconds = (end - start).total_seconds()

    if seconds < 0:
        return None

    return round(seconds / 60)


def get_event_time(data):
    """
    Obtiene el timestamp que determina el orden cronológico
    del evento.

    START  -> start_time
    FINISH -> end_time
    """

    status = (data.get("status") or "").lower()

    if status == "started":
        return parse_timestamp(data.get("start_time"))

    if status in {"finished", "ended", "stopped"}:
        return parse_timestamp(data.get("end_time"))

    # Fallback para formatos antiguos
    return (
        parse_timestamp(data.get("start_time"))
        or parse_timestamp(data.get("end_time"))
    )


# ============================================================
# GENERACIÓN DE TASK ID
# ============================================================

def generate_task_id(data, json_file):
    """
    Genera un identificador único para una ejecución.

    Si posteriormente Shortcut envía task_id, se respeta.
    Si no existe, se genera usando timestamp + nombre del archivo.
    """

    existing_id = data.get("task_id")

    if existing_id:
        return str(existing_id)

    timestamp = (
        data.get("start_time")
        or data.get("end_time")
        or "unknown"
    )

    # Elimina caracteres problemáticos
    safe_timestamp = (
        timestamp
        .replace(":", "")
        .replace("-", "")
        .replace("+", "")
        .replace(".", "")
    )

    return f"{safe_timestamp}_{json_file.stem}"


# ============================================================
# CARGAR EVENTOS
# ============================================================

def load_events():
    """
    Lee todos los JSON de task_events y los devuelve
    ordenados cronológicamente.
    """

    if not TASKS_DIR.exists():
        print(f"ℹ️ No existe la carpeta {TASKS_DIR}")
        return []

    events = []

    for json_file in TASKS_DIR.glob("*.json"):

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

        except json.JSONDecodeError:
            print(f"⚠️ JSON inválido: {json_file}")
            continue

        except Exception as e:
            print(f"⚠️ Error leyendo {json_file}: {e}")
            continue

        if not isinstance(data, dict):
            print(f"⚠️ JSON no contiene un objeto: {json_file}")
            continue

        status = (data.get("status") or "").lower()

        if status not in {
            "started",
            "finished",
            "ended",
            "stopped",
        }:
            print(
                f"⚠️ Estado desconocido en {json_file}: "
                f"{status}"
            )
            continue

        event_time = get_event_time(data)

        if event_time is None:
            print(
                f"⚠️ No se pudo determinar fecha/hora: "
                f"{json_file}"
            )
            continue

        events.append({
            "file": json_file,
            "data": data,
            "time": event_time,
        })

    # Orden cronológico
    events.sort(
        key=lambda event: (
            event["time"],
            event["file"].name
        )
    )

    return events


# ============================================================
# PROCESAMIENTO
# ============================================================

def process_tasks():
    """
    Procesa los eventos.

    Regla principal:

        START
            ↓
        agrega tarea a tareas activas

        FINISH
            ↓
        finaliza la última tarea activa

    Es decir, FINISH funciona como una pila (LIFO).
    """

    events = load_events()

    if not events:
        print("ℹ️ No hay eventos para procesar")
        return

    # --------------------------------------------------------
    # Tareas activas
    #
    # La última tarea agregada será la primera en finalizar.
    # --------------------------------------------------------

    active_tasks = []

    # Todas las tareas finalizadas
    completed_tasks = []

    # Para evitar problemas con eventos duplicados
    processed_event_files = set()

    # --------------------------------------------------------
    # Procesar eventos cronológicamente
    # --------------------------------------------------------

    for event in events:

        json_file = event["file"]
        data = event["data"]

        # Evitar procesar dos veces el mismo archivo
        if json_file.name in processed_event_files:
            continue

        processed_event_files.add(json_file.name)

        status = (data.get("status") or "").lower()

        # ====================================================
        # START
        # ====================================================

        if status == "started":

            task_id = generate_task_id(
                data,
                json_file
            )

            start_time = data.get("start_time")

            task = {
                "task_id": task_id,
                "fecha": (
                    start_time.split("T")[0]
                    if start_time and "T" in start_time
                    else ""
                ),
                "tarea": (
                    data.get("task_name")
                    or data.get("task")
                    or ""
                ),
                "hora_inicio": start_time or "",
                "hora_termino": "",
                "duracion_minutos": "",
                "categoria": (
                    data.get("category")
                    or ""
                ),
                "notas": (
                    data.get("notes")
                    or ""
                ).strip(),
            }

            active_tasks.append(task)

            print(
                f"▶️ START | "
                f"{task['task_id']} | "
                f"{task['tarea']} | "
                f"{task['hora_inicio']}"
            )

        # ====================================================
        # FINISH
        # ====================================================

        elif status in {
            "finished",
            "ended",
            "stopped",
        }:

            end_time = data.get("end_time")

            if not end_time:
                print(
                    f"⚠️ Evento de término sin end_time: "
                    f"{json_file}"
                )
                continue

            # ------------------------------------------------
            # REGLA PRINCIPAL:
            #
            # La última tarea iniciada que todavía está activa
            # es la que se finaliza.
            # ------------------------------------------------

            if not active_tasks:

                print(
                    f"⚠️ FINISH sin tarea activa: "
                    f"{json_file}"
                )

                continue

            task = active_tasks.pop()

            task["hora_termino"] = end_time

            duration = get_duration_minutes(
                task["hora_inicio"],
                end_time
            )

            task["duracion_minutos"] = (
                duration
                if duration is not None
                else ""
            )

            completed_tasks.append(task)

            print(
                f"⏹️ FINISH | "
                f"{task['task_id']} | "
                f"{task['tarea']} | "
                f"{end_time} | "
                f"{duration} min"
            )

    # ========================================================
    # TAREAS QUE SIGUEN ABIERTAS
    # ========================================================

    for task in active_tasks:

        completed_tasks.append(task)

        print(
            f"⏳ ABIERTA | "
            f"{task['task_id']} | "
            f"{task['tarea']} | "
            f"{task['hora_inicio']}"
        )

    # ========================================================
    # SI NO HAY TAREAS
    # ========================================================

    if not completed_tasks:
        print("ℹ️ No hay tareas para guardar")
        return

    # ========================================================
    # ORDENAR CSV
    # ========================================================

    completed_tasks.sort(
        key=lambda task: (
            task["hora_inicio"] or ""
        )
    )

    # ========================================================
    # CREAR DIRECTORIO
    # ========================================================

    CSV_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # ========================================================
    # COLUMNAS
    # ========================================================

    fieldnames = [
        "task_id",
        "fecha",
        "tarea",
        "hora_inicio",
        "hora_termino",
        "duracion_minutos",
        "categoria",
        "notas",
    ]

    # ========================================================
    # ESCRIBIR CSV
    # ========================================================

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(completed_tasks)

    # ========================================================
    # RESUMEN
    # ========================================================

    finished_count = sum(
        1
        for task in completed_tasks
        if task["hora_termino"]
    )

    open_count = sum(
        1
        for task in completed_tasks
        if not task["hora_termino"]
    )

    print()
    print("========================================")
    print("       PROCESAMIENTO COMPLETADO")
    print("========================================")
    print(f"Total tareas : {len(completed_tasks)}")
    print(f"Finalizadas  : {finished_count}")
    print(f"Abiertas     : {open_count}")
    print(f"CSV          : {CSV_FILE}")
    print("========================================")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    process_tasks()
