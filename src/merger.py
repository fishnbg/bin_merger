import struct
import binascii
import os

AIO_MAGIC = b"AIOH"
ELAN_VENDOR_ID = 0x04F3
ELAN_PRODUCT_ID = b"\x08\x56"
CRC32_POLY = 0xEDB88320  # binascii.crc32 uses this polynomial implicitly

def calculate_crc32(data: bytes) -> int:
    """Calculate CRC32 for the given data."""
    return binascii.crc32(data) & 0xFFFFFFFF

def generate_aio_header(fw_count: int) -> bytes:
    """
    Generate AIO Header (0x20 bytes)
    Offset Sizes:
    0x00: Magic (4B) "AIOH"
    0x04: Version (2B) 0x0001
    0x06: Header Size (2B) = 0x20 + (fw_count * 0x50)
    0x08: Device Type (1B) 0x01
    0x09: AIO FW Version (4B) 0x12345678 (Example)
    0x0D: Update Control (1B) 0x00
    0x0E: FW Count (1B)
    0x0F: Reserved (17B) 0xFF
    """
    total_header_size = 0x20 + (fw_count * 0x50)
    magic = AIO_MAGIC
    version = b"\x01\x00"  # Little Endian 0x0001
    header_size = struct.pack("<H", total_header_size) # 2B
    dev_type = b"\x01"
    fw_version = b"\x78\x56\x34\x12" # 0x12345678 Little Endian
    update_ctrl = b"\x00"
    fw_count_byte = struct.pack("<B", fw_count)
    reserved = b"\xFF" * 17
    
    header = magic + version + header_size + dev_type + fw_version + update_ctrl + fw_count_byte + reserved
    assert len(header) == 0x20
    return header

def generate_elan_header(fw_offset: int, fw_size: int, crc32_val: int) -> bytes:
    """
    Generate ELAN Header (0x50 bytes)
    """
    # Initialize with 0x00
    header = bytearray(0x50)
    
    # 0x0000 Vendor ID 0x04F3
    struct.pack_into("<H", header, 0x0000, ELAN_VENDOR_ID)
    
    # 0x0022 Product ID 0x08, 0x56
    header[0x0022:0x0024] = ELAN_PRODUCT_ID
    
    # 0x0024 Unique ID 0xFF, 0xFF
    header[0x0024:0x0026] = b"\xFF\xFF"
    
    # 0x0026 FW Version 0x12, 0x34
    header[0x0026:0x0028] = b"\x34\x12"  # Little endian
    
    # 0x0028 FW Data Offset (4B)
    struct.pack_into("<I", header, 0x0028, fw_offset)
    
    # 0x002C FW Size (4B)
    struct.pack_into("<I", header, 0x002C, fw_size)
    
    # 0x0030 CRC32 (16B total, 4B crc + 12B pad)
    struct.pack_into("<I", header, 0x0030, crc32_val)
    # Remaining 12 bytes of CRC region are already 0x00 since we used bytearray
    
    # 0x0040 Reserved (16B) -> Fill with 0xFF
    for i in range(0x40, 0x50):
        header[i] = 0xFF
        
    return bytes(header)



def merge_binaries(targets: list[dict], output_filepath: str):
    """
    targets is a list of dicts: [{"path": "fw1.bin", "offset": 0x1000}, ...]
    If offset is 0 or less than all headers, it will be padded automatically.
    """
    fw_count = len(targets)
    total_header_size = 0x20 + (fw_count * 0x50)
    
    # 1. Gather all file data
    fw_data_list = []
    current_offset = total_header_size
    
    for target in targets:
        filepath = target["path"]
        offset = target.get("offset")
        
        with open(filepath, "rb") as f:
            data = f.read()

        # Offset rules:
        # 1. offset is None: Append to the end of the previous binary (auto-append).
        # 2. offset < total_header_size: Force user to place it *after* headers to prevent corrupting headers.
        # 3. Explicit offset >= total_header_size: Place it exactly where asked, potentially overlapping/overwriting older data.
        if offset is None:
            offset = max(current_offset, total_header_size)
        elif offset < total_header_size:
            offset = total_header_size
            
        size = len(data)
        fw_data_list.append({
            "data": data,
            "offset": offset,
            "size": size
        })
        
        current_offset = offset + size
        
    # 2. Construct the final binary (data only first)
    # We create a bytearray up to the maximum offset + size
    max_end = total_header_size
    for target in fw_data_list:
        end_pos = target["offset"] + target["size"]
        if end_pos > max_end:
            max_end = end_pos
            
    final_bin = bytearray(max_end)
    
    # Copy FW data to final_bin to resolve overlaps (later targets overwrite earlier ones)
    for target in fw_data_list:
        ofs = target["offset"]
        sz = target["size"]
        final_bin[ofs:ofs+sz] = target["data"]
        
    # 3. Calculate CRC based on the resolved overlapping data
    for target in fw_data_list:
        ofs = target["offset"]
        sz = target["size"]
        target["crc"] = calculate_crc32(final_bin[ofs:ofs+sz])
        
    # 4. Generate AIO Header
    aio_header = generate_aio_header(fw_count)
    
    # 5. Generate ELAN Headers
    elan_headers = b""
    for target in fw_data_list:
        elan_headers += generate_elan_header(target["offset"], target["size"], target["crc"])
        
    # 6. Copy headers definitively at 0x0000
    final_bin[0:total_header_size] = aio_header + elan_headers
    
    with open(output_filepath, "wb") as f:
        f.write(final_bin)
        
    return total_header_size, max_end
