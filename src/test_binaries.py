import os
from merger import merge_binaries, AIO_MAGIC

def create_dummy_file(filename, size, fill_byte):
    with open(filename, "wb") as f:
        f.write(bytes([fill_byte]) * size)

def test_merger():
    test_dir = "test_data"
    os.makedirs(test_dir, exist_ok=True)
    
    fw1_file = os.path.join(test_dir, "fw1.bin")
    fw2_file = os.path.join(test_dir, "fw2.bin")
    output_file = os.path.join(test_dir, "merged.bin")
    
    # Create dummy target files
    # fw1 will be at offset None (auto append, should be placed at header_size)
    # fw2 will overlap fw1 at 0x100 (explicit index, inside fw1 if fw1 starts at 0xc0)
    # fw3 will explicitly target offset 0, which should bump to header_size and overwrite fw1 exactly
    create_dummy_file(fw1_file, 0x1000, 0xAA)
    create_dummy_file(fw2_file, 0x200, 0xBB)
    
    fw3_file = os.path.join(test_dir, "fw3.bin")
    create_dummy_file(fw3_file, 0x50, 0xCC)
    
    targets = [
        {"path": fw1_file, "offset": None}, # Auto append
        {"path": fw2_file, "offset": 0x100}, # Explicit internal overwrite
        {"path": fw3_file, "offset": 0} # Explicit 0 overwrite (bumping to headers)
    ]
    
    header_size, total_size = merge_binaries(targets, output_file)
    print(f"Merge successful! Header Size: {hex(header_size)}, Total Built Size: {hex(total_size)}")
    
    # Read and verify
    with open(output_file, "rb") as f:
        data = f.read()
        
    assert data[0:4] == AIO_MAGIC
    print("AIO Magic Check Passed")
    
    # FW count
    assert data[0x0E] == 3
    print("FW Count Check Passed")
    
    header_sz = 0x20 + (3 * 0x50)
    
    # Target 1 offset in ELAN Header 0
    import struct
    offset0 = struct.unpack("<I", data[0x20+0x28:0x20+0x28+4])[0]
    assert offset0 == header_sz
    print("Target 1 (fw1) Offset Check Passed")
    
    # Target 2 Offset in ELAN Header 1
    offset1 = struct.unpack("<I", data[0x70+0x28:0x70+0x28+4])[0]
    # Because 0x100 is less than `header_sz` (0x110), it gets force-bumped to `header_sz`
    assert offset1 == header_sz
    print("Target 2 (fw2) Offset Check Passed")
    
    # Target 3 Offset in ELAN Header 2
    offset2 = struct.unpack("<I", data[0xC0+0x28:0xC0+0x28+4])[0]
    assert offset2 == header_sz
    print("Target 3 (fw3) Offset Check Passed (Bumped to header size)")
    
    # Overlap Content Check
    # order: fw1 (auto-append -> header_sz), fw2 (0x100 -> header_sz), fw3 (0 -> header_sz)
    # At offset header_sz, fw3's data (0xCC) dominates because it was added last to the exact same starting point
    assert data[header_sz] == 0xCC
    
    # At offset header_sz + 0x50, fw3 has ended.
    # fw2 is size 0x200. It dominates here because it was added after fw1.
    assert data[header_sz + 0x50] == 0xBB
    
    # At offset header_sz + 0x200, fw2 has ended.
    # fw1 is size 0x1000. It dominates here.
    assert data[header_sz + 0x200] == 0xAA
    
    print("Overlap Overwrite Check Passed")

if __name__ == "__main__":
    test_merger()
