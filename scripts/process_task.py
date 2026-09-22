#!/usr/bin/env python3
import json
import os
import csv
from datetime import datetime
from pathlib import Path

# Directorios
TASKS_DIR = Path("task_events")
CSV_FILE = Path("data/tasks.csv")

def get_duration_minutes(start_time, end_time):
    """Calcula la duración en minutos"""
    if not start_time or not end_time:
        return None
    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        delta = end - start
        return int(delta.total_seconds() / 60)
    except:
        return None

def process_tasks():
    """Procesa todos los archivos JSON de tareas y los consolida en CSV"""
    tasks = []
    
    # Leer todos los archivos JSON
    if TASKS_DIR.exists():
        for json_file in sorted(TASKS_DIR.glob("*.json")):
            try:
                with open(json_file, 'r') as f:
                    task_data = json.load(f)
                    
                    # Asegurar que tienen lo necesario
                    if 'task_name' in task_data:
                        duration = get_duration_minutes(
                            task_data.get('start_time'),
                            task_data.get('end_time')
                        )
                        
                        tasks.append({
                            'fecha': task_data.get('start_time', '').split('T')[0],
                            'tarea': task_data.get('task_name'),
                            'hora_inicio': task_data.get('start_time', ''),
                            'hora_termino': task_data.get('end_time', ''),
                            'duracion_minutos': duration if duration else '',
                            'categoria': task_data.get('category', ''),
                            'notas': task_data.get('notes', '')
                        })
            except json.JSONDecodeError:
                print(f"⚠️  Error leyendo {json_file}")
    
    # Escribir CSV
    if tasks:
        CSV_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = ['fecha', 'tarea', 'hora_inicio', 'hora_termino', 'duracion_minutos', 'categoria', 'notas']
        
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(tasks)
        
        print(f"✅ {len(tasks)} tareas procesadas y guardadas en {CSV_FILE}")
    else:
        print("ℹ️  No hay tareas para procesar")

if __name__ == "__main__":
    process_tasks()
