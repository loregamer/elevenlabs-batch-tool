#!/bin/bash

echo "Packaging the executable for distribution..."
python package_for_distribution.py
echo ""
read -p "Press Enter to continue..." 