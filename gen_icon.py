"""Generate a folder-style app_icon.ico for File Organizer."""
from PIL import Image, ImageDraw
import os

def draw_folder(size):
    s   = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # ── Colours ──────────────────────────────────────────────────────────
    tab_fill  = (255, 196,  64, 255)   # bright-yellow tab
    body_fill = (255, 214,  96, 255)   # lighter yellow body
    body_shad = (230, 165,  32, 255)   # darker bottom strip
    tab_dark  = (200, 140,  18, 255)   # tab outline
    outline   = (170, 110,   8, 255)   # body outline

    # ── Proportions ───────────────────────────────────────────────────────
    pad     = max(1, round(s * 0.06))
    tab_h   = round(s * 0.20)
    tab_w   = round(s * 0.42)
    tab_r   = max(1, round(s * 0.07))
    body_y0 = round(s * 0.26)
    body_r  = max(1, round(s * 0.09))
    bx0     = pad
    bx1     = s - pad
    by0     = body_y0
    by1     = s - pad
    tx0     = pad
    tx1     = pad + tab_w
    ty0     = pad
    ty1     = body_y0 + body_r          # overlap tab into body

    # ── Tab ───────────────────────────────────────────────────────────────
    d.rounded_rectangle([tx0, ty0, tx1, ty1], radius=tab_r, fill=tab_fill)

    # ── Body ──────────────────────────────────────────────────────────────
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=body_r, fill=body_fill)

    # ── Bottom shadow strip ───────────────────────────────────────────────
    shad_h = round(s * 0.18)
    d.rounded_rectangle([bx0, by1 - shad_h, bx1, by1],
                        radius=body_r, fill=body_shad)

    # ── Outlines ──────────────────────────────────────────────────────────
    lw = max(1, round(s * 0.03))
    d.rounded_rectangle([tx0, ty0, tx1, ty1], radius=tab_r,
                        outline=tab_dark, width=lw)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=body_r,
                        outline=outline,  width=lw)

    return img


def build_ico(frames_by_size: dict, out_path: str) -> None:
    """Write a proper multi-resolution ICO file manually.

    Each frame is encoded as a raw 32-bpp BITMAPINFOHEADER+pixels chunk
    (classic Windows ICO, no PNG embedding) so every size survives.
    """
    import struct

    chunks = []
    for size, img in sorted(frames_by_size.items()):
        rgba = img.convert("RGBA").tobytes()
        # BITMAPINFOHEADER (40 bytes)
        header = struct.pack(
            "<IIIHHIIIIII",
            40,          # biSize
            size,        # biWidth
            size * 2,    # biHeight (doubled for AND mask)
            1,           # biPlanes
            32,          # biBitCount
            0,           # biCompression (BI_RGB)
            0,           # biSizeImage
            0, 0, 0, 0,  # resolution + colours
        )
        # Pixel data: ICO rows are bottom-up
        rows = [rgba[y * size * 4:(y + 1) * size * 4] for y in range(size)]
        pixels = b"".join(reversed(rows))
        # AND mask: all-zero (fully opaque via alpha channel)
        row_bytes = ((size + 31) // 32) * 4
        and_mask  = b"\x00" * (row_bytes * size)
        chunks.append(header + pixels + and_mask)

    num = len(chunks)
    # Directory starts right after the 6-byte ICO header + num*16-byte entries
    offset = 6 + num * 16
    with open(out_path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, num))   # ICO magic + count
        for (size, _), chunk in zip(sorted(frames_by_size.items()), chunks):
            w = size if size < 256 else 0
            f.write(struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32,
                                len(chunk), offset))
            offset += len(chunk)
        for chunk in chunks:
            f.write(chunk)


def main():
    sizes  = [16, 24, 32, 48, 64, 128, 256]
    frames = {s: draw_folder(s) for s in sizes}
    out    = r"C:\Users\ronde\Documents\Scripts\app_icon.ico"
    build_ico(frames, out)
    print(f"Saved {out}  ({os.path.getsize(out):,} bytes)")


if __name__ == "__main__":
    main()
