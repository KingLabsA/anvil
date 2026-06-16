#!/usr/bin/env python3
"""Generate PNG icons from SVG for browser extension."""

import subprocess
import sys

def check_rsvg():
    """Check if rsvg-convert is available."""
    try:
        subprocess.run(['rsvg-convert', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def generate_icons():
    """Generate PNG icons in different sizes."""
    sizes = [16, 32, 48, 128]
    svg_file = 'icons/icon.svg'
    
    if not check_rsvg():
        print("Warning: rsvg-convert not found. Using placeholder icons.")
        print("Install librsvg to generate proper icons:")
        print("  macOS: brew install librsvg")
        print("  Ubuntu: sudo apt-get install librsvg2-bin")
        
        # Create simple placeholder PNGs
        for size in sizes:
            # Create a simple colored square as placeholder
            import struct
            import zlib
            
            def create_png(width, height, color):
                # PNG signature
                signature = b'\x89PNG\r\n\x1a\n'
                
                # IHDR chunk
                ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
                ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
                ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
                
                # IDAT chunk (image data)
                raw_data = b''
                for y in range(height):
                    raw_data += b'\x00'  # Filter byte
                    for x in range(width):
                        raw_data += bytes(color)
                
                compressed = zlib.compress(raw_data)
                idat_crc = zlib.crc32(b'IDAT' + compressed)
                idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
                
                # IEND chunk
                iend_crc = zlib.crc32(b'IEND')
                iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
                
                return signature + ihdr + idat + iend
            
            # Orange color (245, 158, 11)
            png_data = create_png(size, size, (245, 158, 11))
            
            with open(f'icons/icon{size}.png', 'wb') as f:
                f.write(png_data)
            
            print(f"Created icon{size}.png")
        return
    
    # Use rsvg-convert if available
    for size in sizes:
        output = f'icons/icon{size}.png'
        cmd = [
            'rsvg-convert',
            '-w', str(size),
            '-h', str(size),
            '-o', output,
            svg_file
        ]
        subprocess.run(cmd, check=True)
        print(f"Created icon{size}.png")

if __name__ == '__main__':
    generate_icons()
