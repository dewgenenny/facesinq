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

            # Draw number (large, overlaid, no box)
            try:
                # Big font for visibility (Pillow >= 10.0.0)
                font = ImageFont.load_default(size=80)
            except TypeError:
                 # Fallback for older Pillow
                font = ImageFont.load_default() 

            text = str(idx + 1)
            text_x = x + 20
            text_y = y + 10
            
            # Simple outline/shadow for contrast against photos
            shadow_color = "black"
            main_color = "cyan"
            thick = 3
            
            # Draw outline
            for off_x in range(-thick, thick+1):
                for off_y in range(-thick, thick+1):
                    draw.text((text_x + off_x, text_y + off_y), text, font=font, fill=shadow_color)
            
            # Draw main text
            draw.text((text_x, text_y), text, font=font, fill=main_color)
            
        # Convert to bytes
        output = io.BytesIO()
        grid_img.save(output, format='JPEG', quality=85)
        return output.getvalue()

    except Exception as e:
        logger.error(f"Grid generation failed: {e}")
        return None
