import os
import zipfile
import shutil
from datetime import datetime

# Define the files to include in the distribution
files_to_include = [
    "dist/ElevenLabs_Batch_Converter.exe",
    "EXECUTABLE_GUIDE.md",
    "README.md",
    "output/",  # Include the output directory (will be empty)
]

# Create a timestamp for the zip file name
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
zip_filename = f"ElevenLabs_Batch_Converter_{timestamp}.zip"

# Create a temporary directory for packaging
temp_dir = "dist_package"
if os.path.exists(temp_dir):
    shutil.rmtree(temp_dir)
os.makedirs(temp_dir)

# Copy files to the temporary directory
for file_path in files_to_include:
    if file_path.endswith('/'):  # It's a directory
        dir_name = file_path.rstrip('/')
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        dest_dir = os.path.join(temp_dir, os.path.basename(dir_name))
        if os.path.exists(dir_name):
            shutil.copytree(dir_name, dest_dir)
        else:
            os.makedirs(dest_dir)
    else:  # It's a file
        if os.path.exists(file_path):
            dest_file = os.path.join(temp_dir, os.path.basename(file_path))
            shutil.copy2(file_path, dest_file)
        else:
            print(f"Warning: {file_path} does not exist and will not be included in the package.")

# Create the zip file
with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, temp_dir)
            zipf.write(file_path, arcname)

# Clean up the temporary directory
shutil.rmtree(temp_dir)

print(f"Package created: {zip_filename}")
print("The package contains:")
print("- ElevenLabs_Batch_Converter.exe (the executable)")
print("- EXECUTABLE_GUIDE.md (instructions for using the executable)")
print("- README.md (general information about the application)")
print("- output/ (empty directory for converted files)") 