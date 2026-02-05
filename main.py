#!/usr/bin/env python
import warnings
warnings.filterwarnings("ignore", message="Core Pydantic V1")
import sys
sys.path.insert(0, "backend")
from main import cli

if __name__ == "__main__":
    cli()
