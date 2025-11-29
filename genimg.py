#!/usr/bin/env python3
import sys
import cairosvg
import re
from models import get_response

def extract_svg(text):
    """Extract SVG code from the response"""
    # Try to find SVG between ```svg and ``` or just <svg> tags
    svg_match = re.search(r'```(?:svg)?\s*(.*?)```', text, re.DOTALL)
    if svg_match:
        return svg_match.group(1).strip()
    
    # Try to find raw SVG tags
    svg_match = re.search(r'(<svg.*?</svg>)', text, re.DOTALL)
    if svg_match:
        return svg_match.group(1)
    
    # If nothing found, assume the whole response is SVG
    return text.strip()

def main():
    if len(sys.argv) != 4:
        print("Usage: python genimg.py <model> <output_path> <prompt>")
        print('Example: python genimg.py openai/gpt-4 output.png "draw a pelican"')
        sys.exit(1)
    
    model = sys.argv[1]
    output_path = sys.argv[2]
    prompt = sys.argv[3]
    
    # Create a prompt that asks for SVG code
    full_prompt = f"""Generate SVG code for: {prompt}
    
    Requirements:
    - Return only valid SVG code
    - Use a viewBox of "0 0 500 500"
    - Keep it simple and clean
    - Include colors
    
    Return ONLY the SVG code, nothing else."""
    

    # Call the LLM
    response = get_response(model, full_prompt)
    
    # Extract SVG from response
    svg_code = extract_svg(response)
    
    # Ensure it has proper SVG tags
    if not svg_code.startswith('<svg'):
        svg_code = f'<svg viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">\n{svg_code}\n</svg>'
    
    # Convert SVG to PNG
    cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), write_to=output_path)
    
    print(f"✅ Image saved to {output_path}")
        


if __name__ == "__main__":
    main()
