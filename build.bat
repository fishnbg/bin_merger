@echo off
echo Building Binary Merger exe...
python -m PyInstaller --noconfirm --onedir --windowed --name "BinaryMerger" src\main.py
copy src\layout_config.json dist\BinaryMerger\
copy src\style.qss dist\BinaryMerger\
echo Build complete! The executable is in the dist folder.
