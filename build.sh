#!/bin/bash

echo "Installing required packages..."
pip install -r requirements.txt

echo "Building executable..."
python build_exe.py

echo ""
echo "Build process completed!"
echo "The executable can be found in the 'dist' folder."
echo ""
read -p "Press Enter to continue..." 