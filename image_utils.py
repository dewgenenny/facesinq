from PIL import Image, ImageDraw, ImageFont
import io
import requests
import logging

logger = logging.getLogger(__name__)

def generate_grid_image_bytes(image_urls):
    """
    Downloads 4 images and stitches them into a 2x2 grid.
    Returns the bytes of the resulting execution-safe JPEG.
    """
    try:
        images = []
        for url in image_urls:
            try:
                # Use a smaller version if available (optimization) but we likely have 512px
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content))
                    images.append(img)
                else:
                    logger.warning(f"Failed to fetch image: {url} - Status: {resp.status_code}")
                    images.append(None) # Handle missing images?
            except Exception as e:
                logger.error(f"Error fetching image {url}: {e}")
                images.append(None)

        # Create a blank canvas (e.g., 512x512 or 1024x1024 depending on input)
        # Let's standardize on 512x512 quadrants -> 1024x1024 total
        # Or 256x256 quadrants -> 512x512 total (Slack limits)
        
        target_size = (400, 400) # Each quadrant size
        grid_width = target_size[0] * 2
        grid_height = target_size[1] * 2
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color='white')
        
        draw = ImageDraw.Draw(grid_img)
        # Font for numbers
        try:
            # Try to load a default font, size depends on system. 
            # Pillow uses simplistic default font if path not specified.
            # Loading truetype needs a path. Let's use default for now or a large ratio.
            font = ImageFont.load_default() 
            # Default font is tiny. We need to draw big numbers.
            # Without a .ttf file in the container/system, scalable fonts are hard.
            # We will rely on position instead of numbers on image? 
            # Or just draw simple rectangles/lines.
            
            # Actually, standard Pillow default font is bitmap and unscalable.
            # We can draw the number clearly if we had a font.
            # Let's Skip intricate numbers for now and just rely on the 2x2 layout.
            pass
        except:
            pass

        positions = [
            (0, 0), (target_size[0], 0),
            (0, target_size[1]), (target_size[0], target_size[1])
        ]
        
        for idx, img_obj in enumerate(images):
            if idx >= 4: break
            
            x, y = positions[idx]
            
            if img_obj:
                # Resize and Paste
                img_resized = img_obj.resize(target_size, Image.LANCZOS)
                grid_img.paste(img_resized, (x, y))
            else:
                # Draw placeholder
                draw.rectangle([x, y, x + target_size[0], y + target_size[1]], fill="grey")
                draw.text((x + 50, y + 50), "N/A", fill="white")

            # Draw Number Overlay (1, 2, 3, 4)
            # Since we lack a scalable font, let's draw a small box in the corner with the number
            # Or just assume Top-L=1, Top-R=2 etc.
            # Let's draw a white circle with black text in Top-Left of each quadrant
            
            # Simple rectangle background for number
            draw.rectangle([x, y, x + 40, y + 40], fill="white")
            # Draw number (small default font better than nothing)
            draw.text((x + 15, y + 10), str(idx + 1), fill="black")
            
        # Convert to bytes
        output = io.BytesIO()
        grid_img.save(output, format='JPEG', quality=85)
        return output.getvalue()

    except Exception as e:
        logger.error(f"Grid generation failed: {e}")
        return None
