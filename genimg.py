#!/usr/bin/env python3
import sys
import cairosvg
import re
from models import get_response

def extract_svg(text):
    """Extract SVG code from the response, handling various formats"""
    
    # First, try to find SVG in code blocks (```svg, ```xml, or just ```)
    code_block_patterns = [
        r'```(?:svg|xml|html)?\s*\n?(.*?)```',  # Code blocks with optional language
        r'`([^`]*<svg[^`]*</svg>[^`]*)`',       # Inline code with SVG
    ]
    
    for pattern in code_block_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            svg_content = match.group(1).strip()
            # Check if this actually contains SVG
            if '<svg' in svg_content.lower():
                return clean_svg(svg_content)
    
    # Try to find raw SVG tags (most permissive pattern)
    # This handles cases where SVG is embedded in text without code blocks
    svg_pattern = r'<svg[^>]*>.*?</svg>'
    svg_match = re.search(svg_pattern, text, re.DOTALL | re.IGNORECASE)
    if svg_match:
        return clean_svg(svg_match.group(0))
    
    # Try to find partial SVG (starting tag but maybe cut off)
    partial_svg = re.search(r'<svg[^>]*>.*', text, re.DOTALL | re.IGNORECASE)
    if partial_svg:
        svg_content = partial_svg.group(0)
        # If it doesn't have a closing tag, add one
        if '</svg>' not in svg_content.lower():
            svg_content += '</svg>'
        return clean_svg(svg_content)
    
    # Last resort: if the text contains SVG-like elements, try to extract them
    if any(tag in text.lower() for tag in ['<rect', '<circle', '<path', '<polygon', '<ellipse', '<line']):
        # Strip everything before the first SVG element
        for tag in ['<rect', '<circle', '<path', '<polygon', '<ellipse', '<line', '<g', '<defs']:
            if tag in text.lower():
                start_idx = text.lower().index(tag)
                svg_content = text[start_idx:]
                # Wrap in SVG tags if not present
                if not svg_content.lower().startswith('<svg'):
                    svg_content = f'<svg viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">\n{svg_content}\n</svg>'
                return clean_svg(svg_content)
    
    # If nothing found, return the original text (will be wrapped in SVG tags later)
    return text.strip()

def clean_svg(svg_text):
    """Clean and validate SVG content"""
    # Remove any text before <svg tag
    svg_start = svg_text.lower().find('<svg')
    if svg_start > 0:
        svg_text = svg_text[svg_start:]
    
    # Remove any text after </svg> tag
    svg_end = svg_text.lower().rfind('</svg>')
    if svg_end > 0:
        svg_text = svg_text[:svg_end + 6]  # +6 for length of '</svg>'
    
    # Clean up common issues
    svg_text = svg_text.strip()
    
    # Ensure proper closing if cut off
    if '<svg' in svg_text.lower() and '</svg>' not in svg_text.lower():
        svg_text += '</svg>'
    
    return svg_text

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
    

    try:
        # Call the LLM
        print(f"🤖 Generating SVG with {model}...")
        response = get_response(model, full_prompt)
        
        # Extract SVG from response
        svg_code = extract_svg(response)
        
        # Ensure it has proper SVG tags
        if not svg_code.lower().startswith('<svg'):
            # Only wrap if it's not already an SVG
            svg_code = f'<svg viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">\n{svg_code}\n</svg>'
        
        # Validate that we have valid SVG
        if not '<svg' in svg_code.lower():
            print(f"⚠️  Warning: No valid SVG found in response")
            print(f"Response was: {response[:200]}...")
            svg_code = '<svg viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg"><text x="250" y="250" text-anchor="middle">Error: No SVG generated</text></svg>'
        
        # Convert SVG to PNG
        print(f"🎨 Converting SVG to PNG...")
        cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), write_to=output_path)
        
        print(f"✅ Image saved to {output_path}")
        
        # Optionally save the SVG for debugging
        if '--save-svg' in sys.argv:
            svg_path = output_path.rsplit('.', 1)[0] + '.svg'
            with open(svg_path, 'w') as f:
                f.write(svg_code)
            print(f"📝 SVG saved to {svg_path}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        


if __name__ == "__main__":
    main()
