from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import pdfplumber
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import os
import re
from dotenv import load_dotenv
import anthropic

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize Anthropic client (will be None if API key not set)
anthropic_client = None
if os.getenv('ANTHROPIC_API_KEY'):
    anthropic_client = anthropic.Anthropic()

# Load BDI-3 skills mapping from JSON file
import json

def load_skills_mapping():
    """Load the BDI-3 skills mapping from JSON file and flatten it for lookups."""
    json_path = os.path.join(os.path.dirname(__file__), 'bdi3_skills.json')
    with open(json_path, 'r') as f:
        skills_data = json.load(f)

    # Create flat mapping for age lookups
    flat_map = {}
    # Also create a structured mapping for domain/subdomain lookups
    structured_map = skills_data

    for domain, subdomains in skills_data.items():
        for subdomain, skills in subdomains.items():
            for skill, age in skills.items():
                flat_map[skill] = {
                    'age': age,
                    'domain': domain,
                    'subdomain': subdomain
                }

    return flat_map, structured_map

SKILL_AGE_MAP, SKILLS_STRUCTURED = load_skills_mapping()

# Track unmatched skills for debugging
unmatched_skills = []


def find_age_range(skill_text, track_unmatched=True):
    """Find age range for a skill by matching against reference data from template.

    Returns tuple: (age_range, match_type) where match_type is:
    - 'exact': Exact match found
    - 'case_insensitive': Case-insensitive match
    - 'partial': Partial string match
    - 'word_match': Matched by common words
    - 'none': No match found
    """
    global unmatched_skills

    # Clean the skill text
    skill_clean = skill_text.strip().rstrip('.')

    # Try exact match first
    if skill_clean in SKILL_AGE_MAP:
        return SKILL_AGE_MAP[skill_clean]['age'], 'exact'

    # Try case-insensitive exact match
    skill_lower = skill_clean.lower()
    for ref_skill, data in SKILL_AGE_MAP.items():
        if ref_skill.lower() == skill_lower:
            return data['age'], 'case_insensitive'

    # Try partial match (skill contains reference or vice versa)
    for ref_skill, data in SKILL_AGE_MAP.items():
        ref_lower = ref_skill.lower()
        if ref_lower in skill_lower or skill_lower in ref_lower:
            return data['age'], 'partial'

    # Try matching by significant words (at least 4 words match)
    skill_words = set(skill_lower.split())
    for ref_skill, data in SKILL_AGE_MAP.items():
        ref_words = set(ref_skill.lower().split())
        common = skill_words & ref_words
        if len(common) >= 4:
            return data['age'], 'word_match'

    # No match found - track it for debugging
    if track_unmatched and skill_clean not in unmatched_skills:
        unmatched_skills.append(skill_clean)

    return "", 'none'


def get_match_stats():
    """Return statistics about skill matching."""
    return {
        'total_skills_in_json': len(SKILL_AGE_MAP),
        'unmatched_skills': unmatched_skills.copy(),
        'unmatched_count': len(unmatched_skills)
    }


def clear_unmatched_skills():
    """Clear the unmatched skills list (call before each new PDF)."""
    global unmatched_skills
    unmatched_skills = []


def generate_domain_summary(domain_name, subdomains_data):
    """Generate an AI summary for an entire domain with all its subdomains."""
    if not anthropic_client:
        return None

    # Build data for each subdomain
    subdomain_info = {}
    for subdomain_name, skills in subdomains_data.items():
        mastered = []
        emerging = []
        for skill in skills:
            skill_text = skill['skill']
            if skill['mastery'] == 'MASTERED':
                mastered.append(skill_text)
            elif skill['mastery'] == 'EMERGING':
                emerging.append(skill_text)
        subdomain_info[subdomain_name] = {'mastered': mastered, 'emerging': emerging}

    # Build the data section
    data_section = ""
    for sub_name, info in subdomain_info.items():
        data_section += f"\n{sub_name}:\n"
        if info['mastered']:
            data_section += f"MASTERED: {', '.join(info['mastered'])}\n"
        if info['emerging']:
            data_section += f"EMERGING: {', '.join(info['emerging'])}\n"

    # Domain-specific prompts - plain text only, no markdown
    format_instructions = """

IMPORTANT: Write in plain text only. Do NOT use any markdown formatting like **bold**, *italics*, or bullet points. The text will be pasted directly into a Word document."""

    prompts = {
        "Cognitive": f"""Create 3 paragraphs from this data by sorting skills into sentences for "mastered" and "emerging" for each Cognitive subdomain (Attention & Memory, Reasoning & Academic Skills, Perception & Concepts).

Each paragraph should cover one subdomain. Start each paragraph with the subdomain name followed by a colon.
{format_instructions}

{data_section}""",

        "Adaptive": f"""Create 2 paragraphs from this data by sorting skills into sentences for "mastered" and "emerging" for each Adaptive subdomain (Self Care, Personal Responsibility).

Each paragraph should cover one subdomain. Start each paragraph with the subdomain name followed by a colon.
{format_instructions}

{data_section}""",

        "Motor": f"""Create 3 paragraphs from this data by sorting skills into sentences for "mastered" and "emerging" for each Motor subdomain (Gross Motor, Fine Motor, Perceptual Motor).

Each paragraph should cover one subdomain. Start each paragraph with the subdomain name followed by a colon.
{format_instructions}

{data_section}""",

        "Social-Emotional": f"""Create paragraphs from this data by sorting skills into sentences for "mastered" and "emerging" for each Social-Emotional subdomain.

Each paragraph should cover one subdomain. Start each paragraph with the subdomain name followed by a colon.
{format_instructions}

{data_section}"""
    }

    prompt = prompts.get(domain_name, prompts["Social-Emotional"])

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"Error generating summary: {e}")
        return None


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

        # Get font size from request (default to 8pt Arial)
        font_size = request.form.get('font_size', '8')

        # Get AI summary option (default to true if API key is available)
        include_summaries = request.form.get('include_summaries', 'true').lower() == 'true'

        # Clear unmatched skills tracking before parsing new PDF
        clear_unmatched_skills()

        # Parse PDF
        pdf_data = parse_bdi3_pdf(file)

        # Generate HTML tables with font size and optional summaries
        html_tables = generate_html_tables(pdf_data, font_size, include_summaries)

        # Get match statistics
        match_stats = get_match_stats()

        # Count total skills extracted
        total_skills = sum(
            len(skills)
            for domain in pdf_data.values()
            for skills in domain.values()
        )

        # Return HTML with match statistics
        return jsonify({
            'success': True,
            'html': html_tables,
            'stats': {
                'total_skills_extracted': total_skills,
                'skills_in_database': match_stats['total_skills_in_json'],
                'unmatched_count': match_stats['unmatched_count'],
                'unmatched_skills': match_stats['unmatched_skills']
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/match-stats', methods=['GET'])
def match_stats():
    """Return current match statistics (for debugging)."""
    stats = get_match_stats()
    return jsonify(stats)

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
                                    age, match_type = find_age_range(skill)
                                    data[domain][subdomain].append({
                                        'skill': skill,
                                        'mastery': mastery_status,
                                        'age': age,
                                        'match_type': match_type
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
                                        age, match_type = find_age_range(skill)
                                        data[domain][subdomain].append({
                                            'skill': skill,
                                            'mastery': mastery_status,
                                            'age': age,
                                            'match_type': match_type
                                        })

    return data

def generate_html_tables(data, font_size='8', include_summaries=True):
    """Generate HTML tables for display on the website.

    Output format matches the template:
    - Subdomain header row spanning all columns
    - Column headers: Average age skills develop | [Subdomain] | Mastered | Emerging | Future Learning Objective
    - Data rows: Age | Skill | X | X | X
    - AI-generated summary after each subdomain (if enabled)
    """
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
        domain_html += f'  <table class="result-table" style="font-family: Arial, sans-serif; font-size: {font_size}pt;">\n'
        domain_html += '    <tbody>\n'

        # Add each subdomain as rows within the same table
        for subdomain_name, skills in data[domain_name].items():
            if not skills:
                continue

            # Sort skills by age range for proper grouping
            skills_with_ages = []
            for skill_data in skills:
                # Use existing age if available, otherwise look it up
                if 'age' in skill_data and skill_data['age']:
                    age = skill_data['age']
                else:
                    age, _ = find_age_range(skill_data['skill'], track_unmatched=False)
                skills_with_ages.append({**skill_data, 'age': age})

            # Sort by age (using a rough ordering)
            age_order = ['(0-5mths)', '(0-11mths)', '(0-11 mths)', '(6mths-11mths)',
                        '(12mths-17mths)', '(12-17mths)', '(12-23mths)', '(12-23 mths)',
                        '(18mths-2yrs,11mths)', '(18-23 mths)', '(18-23mths)',
                        '(2 yrs)', '(2-3 yrs)', '(2yrs,6mths-3yrs,11mths)',
                        '(3 yrs)', '(4 yrs)', '(4-5 yrs)', '(5 yrs)',
                        '(5-7 yrs)', '(6 yrs)', '(6-7 yrs)', '(7 yrs)', '']

            def age_sort_key(item):
                age = item.get('age', '')
                try:
                    return age_order.index(age)
                except ValueError:
                    return len(age_order)

            skills_with_ages.sort(key=age_sort_key)

            # Header row with subdomain name and column titles
            domain_html += '      <tr class="subdomain-header-row">\n'
            domain_html += f'        <td class="age-header">Average age<br>skills develop</td>\n'
            domain_html += f'        <td class="subdomain-name">{subdomain_name}</td>\n'
            domain_html += '        <td class="mastery-header">Mastered</td>\n'
            domain_html += '        <td class="mastery-header">Emerging</td>\n'
            domain_html += '        <td class="mastery-header">Future<br>Learning<br>Objective</td>\n'
            domain_html += '      </tr>\n'

            # Track previous age to avoid repeating
            prev_age = None

            # Add skill rows
            for skill_data in skills_with_ages:
                domain_html += '      <tr>\n'

                # Age column - only show if different from previous
                current_age = skill_data.get('age', '')
                if current_age != prev_age:
                    domain_html += f'        <td class="age-cell">{current_age}</td>\n'
                    prev_age = current_age
                else:
                    domain_html += '        <td class="age-cell"></td>\n'

                # Skill column
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

        # Generate AI summary for the entire domain
        if include_summaries:
            summary = generate_domain_summary(domain_name, data[domain_name])
            if summary:
                domain_html += '  <div class="summaries-section">\n'
                domain_html += f'    <div class="summary-box" id="summary_{domain_id}">\n'
                domain_html += f'      <div class="summary-header">\n'
                domain_html += f'        <span class="summary-subdomain">{domain_name} Summary</span>\n'
                domain_html += f'        <button class="copy-summary-btn" onclick="copySummary(this)">Copy</button>\n'
                domain_html += f'      </div>\n'
                domain_html += f'      <div class="summary-text">{summary.replace(chr(10), "<br>")}</div>\n'
                domain_html += f'    </div>\n'
                domain_html += '  </div>\n'

        domain_html += '</div>\n'

        html_output.append(domain_html)

    return '\n'.join(html_output)

if __name__ == '__main__':
    # Use environment variable for port (Replit compatibility)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', debug=True, port=port)

