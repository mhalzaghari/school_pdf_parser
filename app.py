from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import pdfplumber
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import os
import re

app = Flask(__name__, static_folder='static')
CORS(app)

# Age range mapping - reference data from BDI-3 assessment
AGE_RANGES = {
    # Adaptive: Self-Care
    "Communicates the need or desire for food": "(12-23mths)",
    "Washes his or her hands": "(2 yrs)",
    "Shows signs of pretoileting readiness": "(3 yrs)",
    "Removes clothing without fasteners": "(3 yrs)",
    "Uses the toilet": "(4 yrs)",
    "Dresses self completely": "(5 yrs)",
    
    # Adaptive: Personal Responsibility
    "Follows simple rules": "(2 yrs)",
    "Uses appropriate behavior in public": "(4 yrs)",
    "Follows safety rules": "(5 yrs)",
    
    # Social-Emotional: Self
    "Shows awareness of self": "(12-23mths)",
    "Shows independence": "(2 yrs)",
    "Shows self-confidence": "(3 yrs)",
    
    # Social-Emotional: Social Interactions and Relationships
    "Interacts with familiar adults": "(12-23mths)",
    "Interacts with peers": "(2 yrs)",
    "Shows empathy": "(3 yrs)",
    "Engages in cooperative play": "(4 yrs)",
    
    # Motor: Gross Motor
    "Walks independently": "(12-23mths)",
    "Runs": "(2 yrs)",
    "Jumps": "(3 yrs)",
    "Hops on one foot": "(4 yrs)",
    "Skips": "(5 yrs)",
    
    # Motor: Fine Motor
    "Uses pincer grasp": "(12-23mths)",
    "Builds tower of blocks": "(2 yrs)",
    "Copies circle": "(3 yrs)",
    "Cuts with scissors": "(4 yrs)",
    "Writes letters": "(5 yrs)",
    
    # Cognitive: Attention and Memory
    "Attends to object or person": "(12-23mths)",
    "Remembers familiar people": "(2 yrs)",
    "Follows two-step directions": "(3 yrs)",
    
    # Cognitive: Reasoning and Academic Skills
    "Matches objects": "(12-23mths)",
    "Sorts by one attribute": "(2 yrs)",
    "Counts objects": "(3 yrs)",
    "Identifies letters": "(4 yrs)",
    "Reads simple words": "(5 yrs)",
}

def find_age_range(skill_text):
    """Find age range for a skill by matching against reference data."""
    # Clean the skill text
    skill_clean = skill_text.strip().rstrip('.')
    
    # Try exact match first
    if skill_clean in AGE_RANGES:
        return AGE_RANGES[skill_clean]
    
    # Try partial match
    for ref_skill, age in AGE_RANGES.items():
        if ref_skill.lower() in skill_clean.lower() or skill_clean.lower() in ref_skill.lower():
            return age
    
    return "(Unknown)"

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/convert', methods=['POST'])
def convert_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not file.filename.endswith('.pdf'):
            return jsonify({'success': False, 'error': 'File must be a PDF'}), 400

        # Get font size from request (default to 10pt)
        font_size = request.form.get('font_size', '10')

        # Parse PDF
        pdf_data = parse_bdi3_pdf(file)

        # Generate HTML tables with font size
        html_tables = generate_html_tables(pdf_data, font_size)

        # Return HTML
        return jsonify({'success': True, 'html': html_tables})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Known BDI-3 subdomain names - used to fix truncated names from PDF extraction
BDI3_SUBDOMAINS = {
    # Social-Emotional domain
    "Adult Interaction": "Adult Interaction",
    "Adult": "Adult Interaction",
    "Peer Interaction": "Peer Interaction",
    "Peer": "Peer Interaction",
    "Self-Concept and Social Role": "Self-Concept and Social Role",
    "Self-Concept and": "Self-Concept and Social Role",
    "Self-Concept": "Self-Concept and Social Role",
    # Adaptive domain
    "Self-Care": "Self-Care",
    "Personal Responsibility": "Personal Responsibility",
    "Personal": "Personal Responsibility",
    # Motor domain
    "Gross Motor": "Gross Motor",
    "Gross": "Gross Motor",
    "Fine Motor": "Fine Motor",
    "Fine": "Fine Motor",
    "Perceptual Motor": "Perceptual Motor",
    "Perceptual": "Perceptual Motor",
    # Cognitive domain
    "Attention and Memory": "Attention and Memory",
    "Attention and": "Attention and Memory",
    "Attention": "Attention and Memory",
    "Reasoning and Academic Skills": "Reasoning and Academic Skills",
    "Reasoning and Academic": "Reasoning and Academic Skills",
    "Reasoning and": "Reasoning and Academic Skills",
    "Reasoning": "Reasoning and Academic Skills",
    "Perception and Concepts": "Perception and Concepts",
    "Perception and": "Perception and Concepts",
    "Perception": "Perception and Concepts",
}

def normalize_subdomain(subdomain_text):
    """Fix truncated subdomain names using known BDI-3 subdomain list."""
    subdomain_text = subdomain_text.strip()

    # Direct match
    if subdomain_text in BDI3_SUBDOMAINS:
        return BDI3_SUBDOMAINS[subdomain_text]

    # Try matching by prefix (for partial extractions)
    for partial, full in BDI3_SUBDOMAINS.items():
        if subdomain_text.startswith(partial) or partial.startswith(subdomain_text):
            return full

    # Return as-is if no match
    return subdomain_text

def parse_bdi3_pdf(file):
    """Parse BDI-3 PDF and extract domain, subdomain, skill, and mastery data."""
    data = {
        "Adaptive": {},
        "Social-Emotional": {},
        "Motor": {},
        "Cognitive": {}
    }

    with pdfplumber.open(file) as pdf:
        # Pages 4-13 contain Item Level Scores (0-indexed: pages 3-12)
        for page_num in range(3, min(13, len(pdf.pages))):
            page = pdf.pages[page_num]

            # Try to extract tables first
            tables = page.extract_tables()

            if tables:
                # Process table data
                for table in tables:
                    for row in table:
                        if not row or len(row) < 2:
                            continue

                        # Debug: print row structure to understand table format
                        print(f"DEBUG Row ({len(row)} cols): {row[:5]}")  # Print first 5 columns

                        # Handle varying column counts - join first columns if subdomain is split
                        if len(row) >= 4:
                            # Check if column structure splits domain:subdomain across columns
                            first_col = str(row[0]).strip() if row[0] else ""

                            # If first column has domain prefix but subdomain might be in next column
                            if ':' in first_col and any(d in first_col for d in ['Adaptive', 'Social', 'Motor', 'Cognitive']):
                                # Domain:Subdomain might be complete or subdomain continues in col 1
                                second_col = str(row[1]).strip() if row[1] else ""

                                # Check if second column looks like continuation of subdomain (not a skill)
                                # Skills typically are longer sentences; subdomain continuations are short
                                if second_col and len(second_col) < 30 and not any(word in second_col.lower() for word in ['mastered', 'emerging', 'future', 'the ', 'a ', 'an ']):
                                    # Likely subdomain continuation - join it
                                    domain_subdomain = first_col + " " + second_col
                                    skill = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                                    mastery = str(row[3]).strip() if len(row) > 3 and row[3] else ""
                                else:
                                    domain_subdomain = first_col
                                    skill = second_col
                                    mastery = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                            else:
                                domain_subdomain = first_col
                                skill = str(row[1]).strip() if row[1] else ""
                                mastery = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                        elif len(row) >= 3:
                            domain_subdomain = str(row[0]).strip() if row[0] else ""
                            skill = str(row[1]).strip() if row[1] else ""
                            mastery = str(row[2]).strip() if row[2] else ""
                        else:
                            continue

                        # Skip header rows
                        if 'DOMAIN' in domain_subdomain.upper() or 'SKILL' in skill.upper():
                            continue

                        # Parse domain and subdomain from first column
                        if ':' in domain_subdomain:
                            match = re.match(r'(Adaptive|Social-Emotional|Motor|Cognitive):\s*(.+)', domain_subdomain, re.IGNORECASE)
                            if match:
                                domain = match.group(1)
                                # Normalize domain name
                                if 'adaptive' in domain.lower():
                                    domain = 'Adaptive'
                                elif 'social' in domain.lower():
                                    domain = 'Social-Emotional'
                                elif 'motor' in domain.lower():
                                    domain = 'Motor'
                                elif 'cognitive' in domain.lower():
                                    domain = 'Cognitive'
                                else:
                                    continue

                                subdomain = normalize_subdomain(match.group(2).strip())

                                # Normalize mastery status
                                mastery_upper = mastery.upper()
                                if 'MASTERED' in mastery_upper:
                                    mastery_status = 'MASTERED'
                                elif 'EMERGING' in mastery_upper:
                                    mastery_status = 'EMERGING'
                                elif 'FUTURE' in mastery_upper:
                                    mastery_status = 'FUTURE LEARNING OBJECTIVE'
                                else:
                                    continue  # Skip rows without valid mastery status

                                # Add to data structure
                                if subdomain not in data[domain]:
                                    data[domain][subdomain] = []

                                if skill and len(skill) > 3:
                                    age = find_age_range(skill)
                                    data[domain][subdomain].append({
                                        'skill': skill,
                                        'mastery': mastery_status,
                                        'age': age
                                    })

            # Also try text extraction with pipe separator
            text = page.extract_text()
            if text:
                lines = text.split('\n')

                for line in lines:
                    line = line.strip()
                    if not line or 'DOMAIN' in line.upper():
                        continue

                    # Try pipe-separated format: Domain:Subdomain | Skill | Mastery
                    if '|' in line:
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 3:
                            domain_subdomain = parts[0]
                            skill = parts[1]
                            mastery = parts[2]

                            # Parse domain and subdomain
                            if ':' in domain_subdomain:
                                match = re.match(r'(Adaptive|Social-Emotional|Motor|Cognitive):\s*(.+)', domain_subdomain, re.IGNORECASE)
                                if match:
                                    domain = match.group(1)
                                    if 'adaptive' in domain.lower():
                                        domain = 'Adaptive'
                                    elif 'social' in domain.lower():
                                        domain = 'Social-Emotional'
                                    elif 'motor' in domain.lower():
                                        domain = 'Motor'
                                    elif 'cognitive' in domain.lower():
                                        domain = 'Cognitive'
                                    else:
                                        continue

                                    subdomain = normalize_subdomain(match.group(2).strip())

                                    # Normalize mastery status
                                    mastery_upper = mastery.upper()
                                    if 'MASTERED' in mastery_upper:
                                        mastery_status = 'MASTERED'
                                    elif 'EMERGING' in mastery_upper:
                                        mastery_status = 'EMERGING'
                                    elif 'FUTURE' in mastery_upper:
                                        mastery_status = 'FUTURE LEARNING OBJECTIVE'
                                    else:
                                        continue

                                    # Add to data structure
                                    if subdomain not in data[domain]:
                                        data[domain][subdomain] = []

                                    if skill and len(skill) > 3:
                                        age = find_age_range(skill)
                                        data[domain][subdomain].append({
                                            'skill': skill,
                                            'mastery': mastery_status,
                                            'age': age
                                        })

    return data

def generate_html_tables(data, font_size='10'):
    """Generate HTML tables for display on the website."""
    html_output = []

    # Process each domain
    for domain_name in ["Adaptive", "Social-Emotional", "Motor", "Cognitive"]:
        if domain_name not in data or not data[domain_name]:
            continue

        # Start wrapper div for this domain
        domain_id = domain_name.lower().replace('-', '_')
        domain_html = f'<div class="domain-section" id="domain_{domain_id}">\n'
        domain_html += f'  <div class="domain-header">\n'
        domain_html += f'    <h3 class="domain-title">{domain_name}</h3>\n'
        domain_html += f'    <button class="copy-btn" data-domain="{domain_id}">Copy Table</button>\n'
        domain_html += f'  </div>\n'
        domain_html += f'  <div class="table-container">\n'

        # Create ONE table for the entire domain with all subdomains
        domain_html += f'  <table class="result-table" style="font-size: {font_size}pt;">\n'
        domain_html += '    <tbody>\n'

        # Add each subdomain as rows within the same table
        for subdomain_name, skills in data[domain_name].items():
            if not skills:
                continue

            # Header row with subdomain name and mastery columns
            domain_html += '      <tr class="subdomain-header-row">\n'
            domain_html += f'        <td class="subdomain-name">{subdomain_name}</td>\n'
            domain_html += '        <td class="mastery-header">Mastered</td>\n'
            domain_html += '        <td class="mastery-header">Emerging</td>\n'
            domain_html += '        <td class="mastery-header">Future Learning Objective</td>\n'
            domain_html += '      </tr>\n'

            # Add skill rows
            for skill_data in skills:
                domain_html += '      <tr>\n'
                domain_html += f'        <td class="skill-cell">{skill_data["skill"]}</td>\n'

                # Add X mark in appropriate column
                mastered = 'X' if skill_data['mastery'] == 'MASTERED' else ''
                emerging = 'X' if skill_data['mastery'] == 'EMERGING' else ''
                future = 'X' if skill_data['mastery'] == 'FUTURE LEARNING OBJECTIVE' else ''

                domain_html += f'        <td class="mastery-cell">{mastered}</td>\n'
                domain_html += f'        <td class="mastery-cell">{emerging}</td>\n'
                domain_html += f'        <td class="mastery-cell">{future}</td>\n'
                domain_html += '      </tr>\n'

        domain_html += '    </tbody>\n'
        domain_html += '  </table>\n'
        domain_html += '  </div>\n'
        domain_html += '</div>\n'

        html_output.append(domain_html)

    return '\n'.join(html_output)

if __name__ == '__main__':
    # Use environment variable for port (Replit compatibility)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', debug=True, port=port)

