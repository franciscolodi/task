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

FIELDNAMES = [
    "task_id",
    "fecha",
    "tarea",
    "hora_inicio",
    "hora_termino",
    "duracion_minutos",
    "categoria",
    "notas",
]


# ============================================================
# FECHA / HORA
# ============================================================

def parse_timestamp(value):
    """
    Convierte una fecha ISO 8601 en datetime.

    Ejemplo:
        2026-09-22T12:07:47
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
    Calcula la duración en minutos.
    """

    start = parse_timestamp(start_time)
    end = parse_timestamp(end_time)

    if start is None or end is None:
        return None

    seconds = (
        end - start
    ).total_seconds()

    if seconds < 0:
        return None

    return round(seconds / 60)


# ============================================================
# ID
# ============================================================

def generate_task_id(data, json_file):
    """
    Usa task_id si existe.

    Si no existe, genera uno usando
    la fecha de inicio y el nombre del archivo.
    """

    if data.get("task_id"):
        return str(data["task_id"])

    timestamp = (
        data.get("start_time")
        or data.get("end_time")
        or "unknown"
    )

    safe_timestamp = (
        timestamp
        .replace(":", "")
        .replace("-", "")
        .replace("+", "")
        .replace(".", "")
    )

    return (
        f"{safe_timestamp}_"
        f"{json_file.stem}"
    )


# ============================================================
# LEER EVENTOS
# ============================================================

def load_events():

    if not TASKS_DIR.exists():

        print(
            f"❌ No existe la carpeta: "
            f"{TASKS_DIR}"
        )

        return []

    json_files = list(
        TASKS_DIR.glob("*.json")
    )

    print(
        f"📂 JSON encontrados: "
        f"{len(json_files)}"
    )

    events = []

    for json_file in json_files:

        print(
            f"📄 Leyendo: "
            f"{json_file}"
        )

        try:

            with open(
                json_file,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

        except Exception as e:

            print(
                f"❌ Error leyendo "
                f"{json_file}: {e}"
            )

            continue

        if not isinstance(data, dict):

            print(
                f"⚠️ El JSON no contiene "
                f"un objeto: {json_file}"
            )

            continue

        status = (
            data.get("status") or ""
        ).lower().strip()

        if status not in {
            "started",
            "finished",
            "ended",
            "stopped",
        }:

            print(
                f"⚠️ Estado desconocido: "
                f"{status}"
            )

            continue

        # --------------------------------------------
        # Determinar fecha del evento
        # --------------------------------------------

        if status == "started":

            timestamp = data.get(
                "start_time"
            )

        else:

            timestamp = data.get(
                "end_time"
            )

        event_time = parse_timestamp(
            timestamp
        )

        if event_time is None:

            print(
                f"⚠️ Fecha inválida en: "
                f"{json_file}"
            )

            print(
                f"   timestamp = {timestamp}"
            )

            continue

        events.append({
            "file": json_file,
            "data": data,
            "time": event_time,
        })

    # --------------------------------------------------------
    # Orden cronológico
    # --------------------------------------------------------

    events.sort(
        key=lambda event: (
            event["time"],
            event["file"].name
        )
    )

    print(
        f"✅ Eventos válidos: "
        f"{len(events)}"
    )

    return events


# ============================================================
# CREAR TAREA
# ============================================================

def create_task(data, json_file):

    start_time = data.get(
        "start_time"
    )

    task_id = generate_task_id(
        data,
        json_file
    )

    task = {
        "task_id": task_id,

        "fecha": (
            start_time.split("T")[0]
            if start_time
            and "T" in start_time
            else ""
        ),

        "tarea": (
            data.get("task_name")
            or data.get("task")
            or ""
        ),

        "hora_inicio": (
            start_time or ""
        ),

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

    return task


# ============================================================
# PROCESAR
# ============================================================

def process_tasks():

    print()
    print(
        "========================================"
    )
    print(
        "       PROCESANDO TAREAS"
    )
    print(
        "========================================"
    )

    events = load_events()

    if not events:

        print(
            "⚠️ No hay eventos para procesar."
        )

        return

    # --------------------------------------------------------
    # PILA DE TAREAS ACTIVAS
    #
    # La última tarea iniciada será la primera
    # en terminar.
    # --------------------------------------------------------

    active_tasks = []

    completed_tasks = []

    # ========================================================
    # PROCESAR EVENTOS
    # ========================================================

    for event in events:

        data = event["data"]
        json_file = event["file"]

        status = (
            data.get("status") or ""
        ).lower().strip()

        # ====================================================
        # START
        # ====================================================

        if status == "started":

            task = create_task(
                data,
                json_file
            )

            active_tasks.append(
                task
            )

            print(
                f"▶️ START | "
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

            end_time = data.get(
                "end_time"
            )

            if not end_time:

                print(
                    f"⚠️ FINISH sin "
                    f"end_time: "
                    f"{json_file}"
                )

                continue

            # ------------------------------------------------
            # REGLA:
            #
            # FINISH termina SIEMPRE la última
            # tarea activa.
            # ------------------------------------------------

            if not active_tasks:

                print(
                    f"⚠️ FINISH sin tareas "
                    f"activas: {json_file}"
                )

                continue

            task = active_tasks.pop()

            task["hora_termino"] = (
                end_time
            )

            duration = (
                get_duration_minutes(
                    task["hora_inicio"],
                    end_time
                )
            )

            task["duracion_minutos"] = (
                duration
                if duration is not None
                else ""
            )

            # ------------------------------------------------
            # Si FINISH trae categoría/notas,
            # las podemos actualizar.
            # ------------------------------------------------

            if data.get("category"):
                task["categoria"] = (
                    data["category"]
                )

            if data.get("notes"):
                task["notas"] = (
                    data["notes"]
                ).strip()

            completed_tasks.append(
                task
            )

            print(
                f"⏹️ FINISH | "
                f"{task['tarea']} | "
                f"{end_time} | "
                f"{duration} min"
            )

    # ========================================================
    # TAREAS ABIERTAS
    # ========================================================

    if active_tasks:

        print()

        print(
            f"⏳ Tareas todavía activas: "
            f"{len(active_tasks)}"
        )

        for task in active_tasks:

            completed_tasks.append(
                task
            )

            print(
                f"   └─ {task['tarea']} | "
                f"{task['hora_inicio']}"
            )

    # ========================================================
    # ORDEN FINAL
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
            fieldnames=FIELDNAMES
        )

        writer.writeheader()

        writer.writerows(
            completed_tasks
        )

    # ========================================================
    # RESULTADO
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
    print(
        "========================================"
    )
    print(
        "       PROCESAMIENTO COMPLETADO"
    )
    print(
        "========================================"
    )

    print(
        f"Total tareas : "
        f"{len(completed_tasks)}"
    )

    print(
        f"Finalizadas  : "
        f"{finished_count}"
    )

    print(
        f"Abiertas     : "
        f"{open_count}"
    )

    print(
        f"CSV          : "
        f"{CSV_FILE}"
    )

    print(
        "========================================"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    process_tasks()
