#!/bin/bash

# Create the app directory and its subdirectories
mkdir -p app/templates app/static/css app/static/js

# Create the required files
touch app/__init__.py app/routes.py app/templates/index.html app/templates/upload.html

# Create the run.py file
touch run.py

# Create the requirements.txt file
touch requirements.txt
