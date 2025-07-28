import fitz  # PyMuPDF
import re
from collections import defaultdict
import json
import sys

def extract_headings(doc):
    """
    Extracts text lines from a PDF document along with their properties
    like font size, font name, bounding box coordinates, and page number.
    Also includes the page width for later centering calculations.
    """
    lines = []
    for page_num, page in enumerate(doc):
        page_width = page.rect.width
        
        blocks = page.get_text("dict")['blocks']
        for b in blocks:
            for l in b.get("lines", []):
                line_text = " ".join([span["text"] for span in l.get("spans", [])]).strip()
                if not line_text:
                    continue
                font_details = [(span["size"], span["font"], span.get("color", 0)) for span in l["spans"] if span["text"].strip()]
                if not font_details:
                    continue
                avg_size = sum(fd[0] for fd in font_details) / len(font_details)
                
                main_font_name = font_details[0][1] 
                main_color = font_details[0][2]
                if len(font_details) > 1:
                    largest_span = max(font_details, key=lambda x: x[0])
                    main_font_name = largest_span[1]
                    main_color = largest_span[2]

                valid_spans = [span for span in l['spans'] if 'bbox' in span]
                if not valid_spans:
                    continue

                # Calculate overall bounding box for the line
                x0 = min(span['bbox'][0] for span in valid_spans)
                x1 = max(span['bbox'][2] for span in valid_spans)
                top = min(span['bbox'][1] for span in valid_spans)
                bottom = max(span['bbox'][3] for span in valid_spans)

                # Check for bold/italic style indicators in font name
                font_name_lower = main_font_name.lower()
                is_bold = 'bold' in font_name_lower or 'black' in font_name_lower
                is_italic = 'italic' in font_name_lower or 'oblique' in font_name_lower

                lines.append({
                    "text": line_text,
                    "font_size": avg_size,
                    "font_name": main_font_name,
                    "color": main_color,
                    "is_bold": is_bold,
                    "is_italic": is_italic,
                    "x0": x0,
                    "x1": x1,
                    "top": top,
                    "bottom": bottom,
                    "page": page_num + 1,
                    "page_width": page_width
                })
    return lines

def detect_title(lines):
    """
    Detects the main title of the document from the extracted lines.
    It uses a scoring system based on font size, position, centering, and word count.
    """
    first_page_lines = [l for l in lines if l["page"] == 1 and l["top"] < 400]

    if not first_page_lines:
        return ""

    all_first_page_font_sizes = [l['font_size'] for l in first_page_lines]
    if not all_first_page_font_sizes:
        return ""
    
    unique_font_sizes = sorted(list(set(all_first_page_font_sizes)), reverse=True)
    
    largest_font_size = unique_font_sizes[0] if unique_font_sizes else 0

    candidates = []
    for l in first_page_lines:
        if not l['text'].strip():
            continue
        if l['text'].endswith('.'):
            continue
        if re.search(r'(.)\1{3,}', l['text']):
            continue
        if len(set(l['text'].split())) < 1:
             continue
        if l['font_size'] < 10:
            continue
        if l['text'].lower().startswith(("table of contents", "contents", "abstract", "introduction", "acknowledgements", "preface")):
            continue

        score = 0
        
        if l['font_size'] == largest_font_size:
            score += 10
        elif l['font_size'] >= largest_font_size * 0.8:
            score += 5
        else:
            score += (l['font_size'] / largest_font_size) * 3

        score += (400 - l['top']) / 40

        # Horizontal Centering
        page_width = l.get('page_width', 600)
        line_center = (l['x0'] + l['x1']) / 2
        page_center = page_width / 2
        
        distance_from_center = abs(line_center - page_center)
        if distance_from_center < 0.1 * page_width:
            score += 4
        elif distance_from_center < 0.2 * page_width:
            score += 2

        word_count = len(l['text'].split())
        if 2 <= word_count <= 15:
            score += 3
        elif word_count == 1 or (16 <= word_count <= 25):
            score += 1

        if l['text'] and l['text'][0].isupper():
            score += 1
        if l['text'].isupper() and word_count <= 10:
            score += 2

        candidates.append({'line': l, 'score': score})

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x['score'], reverse=True)
    best_candidate = candidates[0]['line']
    title_text = best_candidate['text']

    if len(candidates) > 1:
        second_best_candidate_info = candidates[1]
        second_best_line = second_best_candidate_info['line']

        if (second_best_line['top'] - best_candidate['bottom'] < 20 and
            abs(best_candidate['font_size'] - second_best_line['font_size']) < 2 and
            abs(candidates[0]['score'] - second_best_candidate_info['score']) < 5):
            
            if best_candidate['top'] < second_best_line['top']:
                title_text += " " + second_best_line['text']
            else:
                title_text = second_best_line['text'] + " " + title_text

    return title_text.strip()

def score_heading(line, all_lines_by_page, all_lines):
    """
    Scores a line to determine if it's a potential heading.
    Considers length, position, font size relative to page, and common patterns.
    Enhanced protection against detecting bullet points and numbered list items/sentences.
    """
    line_text_stripped = line['text'].strip()

    if len(line_text_stripped) < 3:
        return 0

    bullet_point_only_pattern = re.compile(r'^(?:[\u2022\*\-\–\—>]|\(\s*[a-z]\s*\))(?:\s+|\t+)') 
    if bullet_point_only_pattern.match(line_text_stripped):
        return 0

    if (len(line_text_stripped.split()) > 12 or
        line_text_stripped.endswith('.') or
        line['top'] < 50):
        return 0
    
    content_without_prefix = re.sub(r'^\s*(?:\d+(?:\.\d+)*\.?|[IVXLCDM]+\.?|[A-Z]\.?|\([a-z]\))\s*', '', line_text_stripped)
    
    if not content_without_prefix:
        return 0
    
    small_words = {'a', 'an', 'the', 'and', 'or', 'but', 'nor', 'for', 'yet', 'so', 'at', 'by', 'in', 'of', 'on', 'to', 'up', 'as', 'is', 'it', 'with', 'from'}
    words_in_content = content_without_prefix.split()
    if words_in_content:
        lowercase_significant_words = sum(
            1 for word in words_in_content 
            if word and word[0].islower() and word.lower() not in small_words
        )
        total_significant_words = sum(1 for word in words_in_content if word.lower() not in small_words)

        if total_significant_words > 0 and (lowercase_significant_words / total_significant_words) > 0.3:
            return 0

    score = 0

    if re.match(r'^([0-9]+\.)+(\s|$)', line_text_stripped) or re.match(r'^[IVX]+\.', line_text_stripped):
        score += 3
    
    size_rank = sum(1 for l in all_lines_by_page[line['page']] if l['font_size'] < line['font_size'])
    score += size_rank / max(len(all_lines_by_page[line['page']]), 1) * 3

    if 'x0' in line and 'x1' in line:
        if line['x0'] < 100:
            score += 1
        if (line['x1'] - line['x0']) > 200:
            score += 1

    if line.get('is_bold', False):
        score += 2
    if line.get('is_italic', False):
        score += 1

    if sum(1 for l in all_lines if l['text'] == line_text_stripped) > 2:
        score -= 3

    return score

def create_style_signature(line):
    """
    Creates a signature for a line's visual style for similarity comparison.
    Returns the raw values rather than a tuple for flexible similarity checking.
    """
    return {
        'font_size': line['font_size'],
        'font_name': line['font_name'],
        'is_bold': line.get('is_bold', False),
        'is_italic': line.get('is_italic', False),
        'color': line.get('color', 0)
    }

def styles_are_similar(style1, style2, font_size_tolerance=1.5):
    """
    Determines if two style signatures are similar enough to be considered the same cluster.
    
    Args:
        style1, style2: Style dictionaries from create_style_signature
        font_size_tolerance: Maximum difference in font size to consider similar
    
    Returns:
        bool: True if styles should be clustered together
    """
    if abs(style1['font_size'] - style2['font_size']) > font_size_tolerance:
        return False
    def normalize_font_name(font_name):
        base_name = font_name.lower()
        for suffix in ['-bold', '-italic', '-regular', '-light', '-medium', 'bold', 'italic']:
            base_name = base_name.replace(suffix, '')
        return base_name.strip('-').strip()
    
    if normalize_font_name(style1['font_name']) != normalize_font_name(style2['font_name']):
        return False
    
    if style1['is_bold'] != style2['is_bold']:
        return False
    
    if style1['is_italic'] != style2['is_italic']:
        return False
    
    if abs(style1['color'] - style2['color']) > 1000000:  # Rough tolerance for color differences
        return False
    
    return True

def assign_heading_levels_dynamic(headings):
    """
    Dynamically assigns hierarchical levels (H1, H2, H3, etc.) to identified headings
    using dynamic clustering based on visual style similarity.
    
    Algorithm:
    1. Process headings sequentially (by page and position)
    2. For each heading, check if its style is similar to existing clusters
    3. If similar to existing cluster, use that level
    4. If new/different, assign it the next deepest level and add to clusters
    5. Handle numbered headings as special cases
    """
    if not headings:
        return []

    style_clusters = []
    
    max_level_assigned = 0
    
    outline = []
    previous_assigned_level = 0

    for h in headings:
        current_style = create_style_signature(h)
        
        matching_level = None
        for existing_style, level in style_clusters:
            if styles_are_similar(current_style, existing_style):
                matching_level = level
                break
        
        if matching_level is not None:
            current_level = matching_level
        else:
            current_level = max_level_assigned + 1
            style_clusters.append((current_style, current_level))
        
        num_match = re.match(r'^(\d+(?:\.\d+)*)', h['text'])
        if num_match:
            num_level_from_pattern = len(num_match.group(1).split('.'))
            if num_level_from_pattern > current_level:
                current_level = num_level_from_pattern
                if style_clusters and style_clusters[-1][0] == current_style:
                    style_clusters[-1] = (current_style, current_level)
        
        if previous_assigned_level != 0 and current_level > previous_assigned_level + 1:
            current_level = previous_assigned_level + 1
            if style_clusters and style_clusters[-1][0] == current_style:
                style_clusters[-1] = (current_style, current_level)
        
        current_level = max(1, current_level)
        max_level_assigned = max(max_level_assigned, current_level)
        
        outline.append({
            "level": f"H{current_level}",
            "text": h['text'].strip(),
            "page": h['page']
        })
        previous_assigned_level = current_level
    
    return outline

def build_outline_from_toc(doc):
    """
    Builds an outline using the PDF's embedded Table of Contents (TOC).
    """
    toc = doc.get_toc()
    if not toc or len(toc) < 3:
        return None

    outline = []
    for entry in toc:
        level, title, page = entry[:3]
        outline.append({
            "level": f"H{level}",
            "text": title.strip(),
            "page": page
        })

    lines = extract_headings(doc)
    detected_title = detect_title(lines) or ""

    return {
        "title": detected_title,
        "outline": outline
    }

def build_outline_heuristic(doc):
    """
    Builds an outline using heuristic methods with dynamic clustering
    when an embedded TOC is not available or insufficient.
    """
    lines = extract_headings(doc)
    title = detect_title(lines) or ""

    lines_by_page = defaultdict(list)
    for line in lines:
        lines_by_page[line['page']].append(line)

    heading_candidates = []
    for line in lines:
        if line['text'].strip() == title:
            continue
        
        candidate = {
            "text": line['text'],
            "page": line['page'],
            "font_size": line['font_size'],
            "font_name": line['font_name'],
            "color": line.get('color', 0),
            "is_bold": line.get('is_bold', False),
            "is_italic": line.get('is_italic', False),
            "x0": line.get('x0', 0),
            "x1": line.get('x1', 0),
            "top": line['top'],
            "page_width": line.get('page_width', 600)
        }
        
        score = score_heading(candidate, lines_by_page, lines)
        if score >= 3: 
            heading_candidates.append(candidate)

   
    heading_candidates.sort(key=lambda l: (l['page'], l['top']))
    
   
    outline = []
    seen = set()
    for h in assign_heading_levels_dynamic(heading_candidates):
        key = (h['text'], h['page'])
        if key not in seen:
            seen.add(key)
            outline.append(h)

    return {
        "title": title,
        "outline": outline
    }
    
def extract_outline_and_text(pdf_path):
    """
    Extracts the outline and raw page text from a PDF document,
    writes it (optional), and returns the result dictionary.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        dict: {
            "title": str,
            "outline": [...],
            "style_info": ...,
            "page_text": {page_num: text}
        }
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        error_data = {"error": f"Could not open PDF file at {pdf_path}: {e}"}
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(error_data, f, indent=2)
        sys.exit(1)

    result = build_outline_from_toc(doc)
    if not result or not result.get("outline"):
        result = build_outline_heuristic(doc)

    page_text = {i + 1: page.get_text() for i, page in enumerate(doc)}
    result["page_text"] = page_text

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result
