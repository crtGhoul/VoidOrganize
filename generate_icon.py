import os
from PIL import Image, ImageDraw

def create_voidorganize_icon(output_ico_path: str, output_png_path: str):
    """Generate a high-tech Cyber Emerald & Obsidian VoidOrganize icon."""
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []

    for width, height in sizes:
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer rounded dark tile
        margin = max(1, width // 16)
        r = max(2, width // 6)
        
        # Background gradient or dark obsidian box
        draw.rounded_rectangle(
            [margin, margin, width - margin, height - margin],
            radius=r,
            fill="#0f172a", # Slate-900 obsidian
            outline="#10b981", # Cyber Emerald border
            width=max(1, width // 32)
        )

        # Inner folder & sorting layers
        mid_x = width // 2
        mid_y = height // 2
        
        # Grid of organized blocks / folders
        pad = width // 5
        block_w = (width - pad * 2) // 2
        block_h = (height - pad * 2) // 2
        gap = max(2, width // 24)

        # Top-left block (Emerald)
        draw.rounded_rectangle(
            [pad, pad, pad + block_w - gap, pad + block_h - gap],
            radius=max(1, r // 3),
            fill="#10b981"
        )

        # Top-right block (Cyan / Blue)
        draw.rounded_rectangle(
            [pad + block_w, pad, pad + block_w * 2 - gap, pad + block_h - gap],
            radius=max(1, r // 3),
            fill="#06b6d4"
        )

        # Bottom-left block (Indigo / Purple)
        draw.rounded_rectangle(
            [pad, pad + block_h, pad + block_w - gap, pad + block_h * 2 - gap],
            radius=max(1, r // 3),
            fill="#6366f1"
        )

        # Bottom-right block (Crimson accent)
        draw.rounded_rectangle(
            [pad + block_w, pad + block_h, pad + block_w * 2 - gap, pad + block_h * 2 - gap],
            radius=max(1, r // 3),
            fill="#f43f5e"
        )

        # Center holographic sorting diamond
        d_rad = max(2, width // 8)
        diamond = [
            (mid_x, mid_y - d_rad),
            (mid_x + d_rad, mid_y),
            (mid_x, mid_y + d_rad),
            (mid_x - d_rad, mid_y),
        ]
        draw.polygon(diamond, fill="#ffffff", outline="#0f172a")

        images.append(img)

    # Save highest resolution as PNG
    images[0].save(output_png_path, format="PNG")
    # Save multi-resolution ICO
    images[0].save(
        output_ico_path,
        format="ICO",
        sizes=[(s[0], s[1]) for s in sizes],
        append_images=images[1:]
    )
    print(f"[+] Successfully generated icons: {output_ico_path}, {output_png_path}")

if __name__ == "__main__":
    create_voidorganize_icon("icon.ico", "icon.png")
