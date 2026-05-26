import os
import sys

# Programmatically append the backend parent directory to sys.path during collection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
