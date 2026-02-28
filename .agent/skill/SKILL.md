---
name: binary_merger
description: merge binary files with AIO/ELAN header support
---
## Context
Goal: Build a Windows desktop application (Electron/Flutter/PySide6) to merge multiple target binary files into a base binary file at specified offsets, supporting custom firmware headers.

# Skill: Binary File Merger with Custom Layout & Header Management

## Header Specification & Logic

### 1. Pre-Merge Detection (Magic Number Check)
- **Action:** Before merging, read the first 4 bytes of the **Base File**.
- **Condition:** If bytes match `0x41 0x49 0x4F 0x48` ("AIOH"):
    - **Extraction:** Read the `Header Size` at offset `0x0006`.
    - **Processing:** Extract all data starting from `Header Size` position as the "Clean Base Data".
    - **Reconstruction:** Discard the old header; a new one will be generated based on the current merge task.
- **Else:** Treat the entire Base File as raw binary data. And generate a new header based on the current merge task after merged

### 2. All-in-One (AIO) Header (0x20 Bytes)

- **0x0000 (4B):** Magic Number = `0x41, 0x49, 0x4F, 0x48` ("AIOH")
- **0x0004 (2B):** Header Version = `0x0001`
- **0x0006 (2B):** Header Size = `0x20 + (FW_Count * 0x50)` (Total length of AIO + all ELAN headers)
- **0x0008 (1B):** Device Type = `0x01` (Touchpad)
- **0x0009 (4B):** AIO FW Version = `0x12, 0x34, 0x56, 0x78`
- **0x000D (1B):** Update Control = `0x00`
- **0x000E (1B):** FW Count = Total number of merged binary files
- **0x000F (17B):** Reserved = Fill with `0xFF`

### 3. ELAN Header (0x50 Bytes per target)
Each merged file (including the Base File) must have a corresponding ELAN header.
- **0x0000 (2B):** Vendor ID = `0x04F3`
- **0x0022 (2B):** Product ID = `0x08, 0x56`
- **0x0024 (2B):** Unique ID = `0xFF, 0xFF`
- **0x0026 (2B):** FW Version = `0x12, 0x34`
- **0x0028 (4B):** FW Data Offset = Absolute offset of this binary in the final file
- **0x002C (4B):** FW Size = Size of the binary file
- **0x0030 (16B):** CRC = CRC32 of the binary data (Polynomial: `0xEDB88320`). Fill CRC result, then pad remaining 12 bytes with `0x00`.
- **0x0040 (16B):** Reserved = Fill with `0xFF`

---

## UI Layout Strategy
- **Base Layout:** Use a `Flexible` or `Grid` container.
- **Customizable Layout:** Defined in `layout_config.json` or `theme.css`.
- **Button B Action:** Dynamically generate a `MergeRow` (Target_File, Offset).

## Execution Logic
- **Header Generation:** 
1. Calculate total header size.
2. Map all binaries (Base + Targets) to sequential or user-defined offsets.
3. Generate AIO Header, then all ELAN Headers.
- **Data Concatenation:** `[AIO Header] + [ELAN Headers] + [Binary Data 1] + [Binary Data 2]...`
- **Gap Handling:** Fill unallocated space between offsets with `0x00`.

## Agent Instructions
- Enable **Layout Hot-Reload** for `.css` or `.json`.
- Use `ScrollArea` for dynamic rows.
- Ensure all Chinese text in UI uses **繁體中文**.