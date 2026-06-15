#!/usr/bin/env python
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  
BACKEND_DIR = os.path.dirname(CURRENT_DIR)  
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

sys.path.insert(0, PROJECT_ROOT)

def main():
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'diesel_engine_predictor.settings'
    )
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()