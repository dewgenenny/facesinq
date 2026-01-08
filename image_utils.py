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
        
        target_size = (400, 400) # Each quadrant size
        grid_width = target_size[0] * 2
        grid_height = target_size[1] * 2
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color='white')
        
        draw = ImageDraw.Draw(grid_img)
        # Font for numbers - simplified to just position/shapes if font missing
        
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

            # Simple rectangle background for number (1, 2, 3, 4)
            draw.rectangle([x, y, x + 40, y + 40], fill="white")
            # Draw number (roughly centered in box)
            # Default font is very small, but better than nothing.
            # If we had a font file we could load it, but we'll stick to basic.
            draw.text((x + 15, y + 10), str(idx + 1), fill="black")
            
        # Convert to bytes
        output = io.BytesIO()
        grid_img.save(output, format='JPEG', quality=85)
        return output.getvalue()

    except Exception as e:
        logger.error(f"Grid generation failed: {e}")
        return None
