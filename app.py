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

# Age range mapping - comprehensive data from BDI-3 template
# This maps skill descriptions to their expected age ranges
SKILL_AGE_MAP = {
    # Cognitive: Attention & Memory
    'Visually attends to light source moving in 180 degree arc': '(0-5mths)',
    'Turns eyes toward light source moving from side to midline': '(0-5mths)',
    'Visually attends to familiar person 4-6ft away for 5 or more seconds': '(0-5mths)',
    'Visually attend to light source moving in vertical direction': '(6mths-11mths)',
    'Follow an auditory stimulus': '(6mths-11mths)',
    'Follow a visual stimulus': '(6mths-11mths)',
    'The child attends to an ongoing activity for 15 or more seconds': '(12mths-17mths)',
    'The child occupies themselves for 5 minutes': '(12mths-17mths)',
    'Recognizes that a person still exists when out of view': '(18mths-2yrs,11mths)',
    'Uncovers hidden toy': '(18mths-2yrs,11mths)',
    'Searches for removed object': '(18mths-2yrs,11mths)',
    'Remains engaged in an activity for at least 5 minutes': '(3 yrs)',
    'looks at/points to/touch/names pictures in books': '(3 yrs)',
    'occupies themselves for 10 minutes or more without demanding attention': '(3 yrs)',
    'finds an object hidden under one of two cups following a 3 second delay': '(3 yrs)',
    'selects the hand holding a toy following a 10 second delay': '(3 yrs)',
    'locates hidden items in a picture scene, level 1': '(4-5 yrs)',
    'locates hidden items in a picture scene, level 2': '(4-5 yrs)',
    'locates hidden items in a picture scene, level 3': '(4-5 yrs)',
    'Recalls familiar objects': '(4-5 yrs)',
    'Repeats 3-digit sequences in order': '(4-5 yrs)',
    'Recites the alphabet': '(6-7 yrs)',
    'Focuses their attention on one task while being aware of, but not distracted by, surrounding activities': '(6-7 yrs)',
    'Sorts by color, shape, and size on command': '(6-7 yrs)',
    'Repeats four-digit sequences in order': '(6-7 yrs)',
    'Repeats two-digit sequences backward': '(6-7 yrs)',
    'Repeats sequences of four and five pictures from memory with a 15-second delay': '(6-7 yrs)',
    'Repeats sequences of six and seven pictures from memory with a 15-second delay': '(6-7 yrs)',
    'Repeats six-digit sequences': '(6-7 yrs)',
    'Repeats four-digit sequences backward': '(6-7 yrs)',
    # Cognitive: Reasoning & Academic Skills
    'Reaches around a barrier to obtain a toy': '(2 yrs)',
    'Experiments with variations of causal behavior': '(2 yrs)',
    'Pulls a cloth to obtain an object': '(2 yrs)',
    'Shows interest and enjoyment in age-appropriate books/printed materials': '(3 yrs)',
    'Matches colors': '(3 yrs)',
    'Demonstrates how to hold a book in preparation for reading': '(3 yrs)',
    'Names the colors red, yellow, and blue': '(4 yrs)',
    'Identifies sources of common actions': '(4 yrs)',
    'Responds to one and one more': '(4 yrs)',
    'Demonstrates understanding of proper reading direction': '(4 yrs)',
    'Recognizes picture absurdities': '(5 yrs)',
    'Completes a simple pattern': '(5 yrs)',
    'Completes analogies': '(5 yrs)',
    'Answers simple logic questions': '(5 yrs)',
    'Distinguishes between uppercase and lowercase letters': '(6 yrs)',
    'Writes letters that stand for sounds': '(6 yrs)',
    'Counts by rote from 1-40': '(6 yrs)',
    'Blends sounds into words': '(6 yrs)',
    'Expresses their thinking in an organized and logical manner': '(6 yrs)',
    'Reads decodable one-syllable, short vowel words': '(7 yrs)',
    'Adds numbers from 0 through 9': '(7 yrs)',
    'Produces a word that rhymes with a given word': '(7 yrs)',
    'Thinks of multiple solutions to a problem': '(7 yrs)',
    'Solves simple addition word problems': '(7 yrs)',
    # Cognitive: Perception & Concepts
    'Responds positively to physical contact and tactile stimulation': '(0-11mths)',
    'Visually explores the environment': '(0-11mths)',
    'Shows awareness of new situations': '(12-23mths)',
    'Feels and explores objects': '(12-23mths)',
    'Imitates simple facial gestures': '(2 yrs)',
    'Places a circle and a square in a form board': '(2 yrs)',
    'Matches a circle, square, and triangle': '(3 yrs)',
    'Identifies familiar objects by their use': '(3 yrs)',
    'Identifies big and little shapes': '(3 yrs)',
    'Identifies colors of familiar objects not in view': '(3 yrs)',
    'Identifies the longer of two lines': '(4 yrs)',
    'Sorts by color with a demonstration': '(4 yrs)',
    'Sorts forms by shape': '(4 yrs)',
    'Identifies visual differences among similar shapes': '(4 yrs)',
    'Identifies soft, rough, and smooth textures': '(4 yrs)',
    'Identifies simple shapes by touch': '(5 yrs)',
    'Sorts by size with a demonstration': '(5 yrs)',
    'Compares the sizes of familiar objects not in view': '(5 yrs)',
    'Identifies visual differences among similar numerals and letters': '(6 yrs)',
    'Groups objects by shape and color': '(6 yrs)',
    'Identifies past and present activities': '(6 yrs)',
    'Identifies the picture that is different': '(6 yrs)',
    'Understands relative time': '(6 yrs)',
    'Categorizes familiar objects by function': '(7 yrs)',
    'Knows the right and left sides of their body': '(7 yrs)',
    'Understands that brother/sister is a reciprocal relationship': '(7 yrs)',
    'Duplicates 9- and 10-object chains': '(7 yrs)',
    'Conserves length': '(7 yrs)',
    'Conserves two-dimensional space': '(7 yrs)',
    'Differentiates present and future social roles': '(7 yrs)',
    'Selects a picture using problem-solving strategies': '(7 yrs)',
    'Demonstrates the ability to take the perspective of another': '(7 yrs)',
    'Identifies connections among experiences and concepts': '(7 yrs)',
    # Adaptive: Self-Care
    'Eats semi solid food when it is placed in their mouth': '(12-23mths)',
    'Bites through soft food': '(12-23mths)',
    'Feeds self bite-sized pieces of food': '(12-23mths)',
    'Participates in dressing by holding out arms/legs': '(12-23mths)',
    'Dips a spoon in food and brings the spoon to their mouth': '(12-23mths)',
    'Communicates the need/desire for food': '(12-23mths)',
    'Washes their hands': '(2 yrs)',
    'Distinguishes between food items and nonfood items': '(2 yrs)',
    'Removes their shoes by untying or unfastening them without assistance': '(2 yrs)',
    'Participates in brushing their teeth with assistance': '(2 yrs)',
    'Drinks from a cup independently and with little spilling': '(2 yrs)',
    'Shows signs of pre-toileting readiness': '(3 yrs)',
    'Removes clothing without fasteners independently': '(3 yrs)',
    'Washes and dries their hands independently': '(3 yrs)',
    'Expresses a need to use the toilet': '(3 yrs)',
    'Puts on lower body clothing': '(3 yrs)',
    'Has bowel movements in the toilet regularly': '(3 yrs)',
    'Puts on shoes independently': '(3 yrs)',
    'Chooses the appropriate utensil for the food they are eating': '(4 yrs)',
    'Sleeps through the night without wetting the bed': '(4 yrs)',
    'Dresses and undresses independently': '(4 yrs)',
    'Takes care of their own toileting needs': '(4 yrs)',
    'Puts on clothing right-side out and front-side forward and puts shoes on the correct feet without assistance': '(5 yrs)',
    'Places toothpaste on a toothbrush and brushes their own teeth': '(5 yrs)',
    'Engages and zips a zipper independently': '(6-7 yrs)',
    'Combs/brushes their own hair': '(6-7 yrs)',
    'Uses a dull knife to cut and spread food': '(6-7 yrs)',
    'Cuts soft foods with the side of a fork': '(6-7 yrs)',
    'Takes a bath or a shower independently': '(6-7 yrs)',
    # Adaptive: Personal Responsibility
    'Explores their environment safely and independently': '(2-3 yrs)',
    'Understands that hot is dangerous': '(2-3 yrs)',
    'Indicates/describes an illness/ailment/injury to an adult': '(4 yrs)',
    'Shows care when handling something delicate/fragile': '(4 yrs)',
    'Uses appropriate behavior in public settings': '(4 yrs)',
    'Demonstrates caution and avoids common dangers': '(5 yrs)',
    'Responds to instructions given in a small group and begins the task without being reminded': '(5 yrs)',
    'Accesses a computer/tablet/electronic device independently': '(5 yrs)',
    'Initiates and organizes their own activities': '(5 yrs)',
    'Follows established rules when playing simple games': '(5 yrs)',
    'Continues to work on a learning task with minimal guidance': '(6 yrs)',
    'Speaks up for themselves': '(6 yrs)',
    "Asks permission to use others' possessions": '(6 yrs)',
    "Answers 'what-to-do-if' questions involving personal responsibility": '(6 yrs)',
    'Performs common household tasks using appropriate items/tools': '(7 yrs)',
    'Takes care of personal belongings independently': '(7 yrs)',
    'Goes to bed without assistance': '(7 yrs)',
    'Crosses the street safely': '(7 yrs)',
    # Motor: Gross Motor
    'Walks up four stairs with support': '(2 yrs)',
    'Walks down four stairs with support': '(2 yrs)',
    'Runs 10 feet while maintaining balance': '(3 yrs)',
    'Kicks a ball forward while maintaining balance': '(3 yrs)',
    'Throws a ball 5 feet forward with direction': '(3 yrs)',
    'Walks backwards 10 or more steps': '(3 yrs)',
    'Walks up stairs, alternating feet, without assistance from a person': '(3 yrs)',
    'Jumps forward with both feet together': '(3 yrs)',
    'Walks forward two or more steps in a straight line, alternating feet': '(3 yrs)',
    'Imitates bilateral movements of an adult': '(4 yrs)',
    'Walks down stairs, alternating feet, without assistance from a person': '(4 yrs)',
    'Jumps forward three or more times with their feet together': '(5 yrs)',
    'Catches a large ball from 5 feet away, using both hands': '(5 yrs)',
    'Hops forward on one foot without support': '(6-7 yrs)',
    'Stands on each foot alternately with their eyes closed': '(6-7 yrs)',
    'Catches a tennis ball, tossed from 5 feet away, with two hands': '(6-7 yrs)',
    'Skips, alternating feet, for at least 20 feet': '(6-7 yrs)',
    'Walks forward 6 feet, heel-to-toe': '(6-7 yrs)',
    # Motor: Fine Motor
    'Transfers an object from one hand to the other': '(18-23 mths)',
    'Removes forms from a form board': '(18-23 mths)',
    'Picks up a small object with the ends of the thumb and index finger in an overhand approach (neat pincer grasp)': '(2 yrs)',
    'Turns pages in a book': '(2 yrs)',
    'Scribbles': '(3 yrs)',
    'Extends/points with their index finger independent of the thumb and other fingers': '(3 yrs)',
    'Scribbles linear and/or circular patterns': '(3 yrs)',
    'Uses their fingertips to grasp a pencil/crayon': '(3 yrs)',
    'Cuts paper with scissors': '(4 yrs)',
    'Holds paper with one hand while drawing/writing with the other hand': '(4 yrs)',
    'Imitates finger movements': '(4 yrs)',
    'Strings four large beads': '(4 yrs)',
    'Folds a sheet of paper': '(4 yrs)',
    'Cuts with scissors following a line': '(6-7 yrs)',
    'Rotates a pencil in one hand': '(6-7 yrs)',
    'Traces designs with curved edges': '(6-7 yrs)',
    'Traces designs with corners': '(6-7 yrs)',
    # Motor: Perceptual Motor
    'Dumps an object from a bottle': '(2yrs,6mths-3yrs,11mths)',
    'Places two objects in a bottle': '(2yrs,6mths-3yrs,11mths)',
    'Places four rings on a post in any order': '(2yrs,6mths-3yrs,11mths)',
    'Stacks four blocks vertically': '(4 yrs)',
    'Imitates a vertical line': '(4 yrs)',
    'Imitates a horizontal line': '(4 yrs)',
    'Builds a three-block bridge': '(5 yrs)',
    'Copies a circle': '(5 yrs)',
    'Writes their first name': '(5 yrs)',
    'Copies a cross': '(5 yrs)',
    'Imitates a six-block design': '(5 yrs)',
    'Copies the letters O, S, and P': '(6-7 yrs)',
    'Copies the letters T, H, and F': '(6-7 yrs)',
    'Copies numerals 1 through 5': '(6-7 yrs)',
    'Copies a square': '(6-7 yrs)',
    'Copies a triangle': '(6-7 yrs)',
    'Copies the letters A, V, and X': '(6-7 yrs)',
    'Copies a diamond': '(6-7 yrs)',
    'Copies words with uppercase and lowercase letters': '(6-7 yrs)',
}

# Additional skill mappings for Social-Emotional domain
SKILL_AGE_MAP_SE = {
    # Social-Emotional: Adult Interaction
    "Looks at an adult's face": '(0-11mths)',
    'Relaxes when being held': '(0-11mths)',
    'Responds to a familiar adult voice': '(0-11mths)',
    'Shows awareness of other people': '(0-11mths)',
    'Tracks an adult with eyes as adult moves from side to side': '(0-11mths)',
    'Shows a desire for social attention': '(0-11mths)',
    'Explores adult facial features': '(0-11mths)',
    'Reacts to positive adult attention and the withdrawal of attention': '(12-17mths)',
    'Expresses enjoyment of/preference for certain things/activities/situations': '(12-17mths)',
    'Discriminates between familiar and unfamiliar people': '(18-23 mths)',
    'Plays peekaboo': '(18-23 mths)',
    'Shows appropriate affection towards people/pets/possessions': '(2 yrs)',
    'Shows appropriate signs of separation anxiety when removed from their parent/caregiver': '(2 yrs)',
    'Responds positively to adult recognition and encouragement': '(3 yrs)',
    "Mimics a familiar adult's facial expressions": '(3 yrs)',
    'Responds positively when familiar adults/adults in authority initiate social contact': '(3 yrs)',
    "Recognizes an adult's happy/sad emotions": '(4 yrs)',
    'Initiates social contact/interactions with familiar adults': '(4 yrs)',
    "Joins in/imitates an adult's performance of simple tasks": '(5-7 yrs)',
    'Seeks help from adults other than their parents/caregiver': '(5-7 yrs)',
    'Follows adult directions with little/no resistance': '(5-7 yrs)',
    'Follows the rules given by an adult for playing simple group games with peers': '(5-7 yrs)',
    'Solicits feedback from adults': '(5-7 yrs)',
    "Waits patiently for a teacher's/other adult's attention": '(5-7 yrs)',
    'Accepts constructive criticism from an adult': '(5-7 yrs)',
    "Recognizes an adult's expressed complex emotions": '(5-7 yrs)',
    'Recognizes traits of positive role models': '(5-7 yrs)',
    # Social-Emotional: Peer Interaction
    'Shows awareness of the presence of other children': '(2 yrs)',
    'Plays independently in the company of peers': '(2 yrs)',
    'Enjoys playing with other children': '(3 yrs)',
    "Imitates other children's play activities": '(3 yrs)',
    "Mimics/responds to peers' emotions": '(3 yrs)',
    'Responds differently to familiar and unfamiliar children': '(3 yrs)',
    'Initiates social contact with peers during play': '(3 yrs)',
    'Shows sympathy/concern for peers': '(4 yrs)',
    "Plays next to peers, using the same materials, but does not influence/disturb the other children's play": '(4 yrs)',
    'Plays cooperatively with peers': '(5 yrs)',
    'Shows interest in being included in peer groups': '(5 yrs)',
    'Shares property with peers': '(5 yrs)',
    'Engages in highly coordinated pretend play': '(6 yrs)',
    'Willingly takes turns and shares': '(6 yrs)',
    'Actively participates in peer relationships': '(7 yrs)',
    'Plays cooperatively in rule-regulated games with peers': '(7 yrs)',
    'Appropriately uses peers as resources': '(7 yrs)',
    'Offers to help peers': '(7 yrs)',
    'Resolves conflict with peers in a peaceful manner': '(7 yrs)',
    'Identifies the traits of a valued friend': '(7 yrs)',
    'Understands when peers make requests/demands that are not reasonable': '(7 yrs)',
    'Self-discloses to a peer': '(7 yrs)',
    'Understands the positive and negative impact of peer pressure': '(7 yrs)',
    'Seeks out friends for guidance and advice on personal matters': '(7 yrs)',
    # Social-Emotional: Self-Concept & Social Role
    'Smiles/vocalizes in response to adult attention': '(0-11 mths)',
    'Expresses emotions': '(0-11 mths)',
    'Shows awareness of their hands': '(0-11 mths)',
    'Shows awareness of their feet': '(12-23 mths)',
    'Responds to their name': '(12-23 mths)',
    'Self-soothes': '(12-23 mths)',
    'Appropriately communicates positive emotions': '(2 yrs)',
    'Appropriately communicates negative emotions': '(2 yrs)',
    'Exhibits apprehension/fear in new situations': '(2 yrs)',
    'Expresses ownership/possession': '(2 yrs)',
    'Identifies themselves in a mirror': '(2 yrs)',
    'Transitions from one activity/setting to another': '(2 yrs)',
    'Shows pride in their work/accomplishments': '(3 yrs)',
    'Uses symbolic representation in make-believe play': '(3 yrs)',
    'Recovers from distress in a reasonable amount of time when comforted': '(3 yrs)',
    'Willingly tries new things': '(3 yrs)',
    'Initiates social interactions with others': '(4 yrs)',
    'Engages in adult role-playing and imitation': '(4 yrs)',
    'Demonstrates knowledge of their age': '(4 yrs)',
    'States their first and last names': '(5 yrs)',
    'Follows classroom rules and agreements': '(5 yrs)',
    "Recognizes another's need for help and offers assistance": '(5 yrs)',
    'Asserts themselves in socially and culturally acceptable ways': '(6-7 yrs)',
    'Respects the property and rights of others': '(6-7 yrs)',
    "Demonstrates the ability to 'show and tell' without major discomfort": '(6-7 yrs)',
    'Describes his or her feelings': '(6-7 yrs)',
    'Shows moral responsibility': '(6-7 yrs)',
    'Waits patiently for a desired item or event': '(6-7 yrs)',
    'Makes social comparisons': '(6-7 yrs)',
    'Stays on task and works through difficulties and frustrations': '(6-7 yrs)',
    'Independently seeks alternatives to problems': '(6-7 yrs)',
}

# Merge all skill maps
SKILL_AGE_MAP.update(SKILL_AGE_MAP_SE)

def find_age_range(skill_text):
    """Find age range for a skill by matching against reference data from template."""
    # Clean the skill text
    skill_clean = skill_text.strip().rstrip('.')

    # Try exact match first
    if skill_clean in SKILL_AGE_MAP:
        return SKILL_AGE_MAP[skill_clean]

    # Try case-insensitive exact match
    skill_lower = skill_clean.lower()
    for ref_skill, age in SKILL_AGE_MAP.items():
        if ref_skill.lower() == skill_lower:
            return age

    # Try partial match (skill contains reference or vice versa)
    for ref_skill, age in SKILL_AGE_MAP.items():
        ref_lower = ref_skill.lower()
        if ref_lower in skill_lower or skill_lower in ref_lower:
            return age

    # Try matching by significant words (at least 5 words match)
    skill_words = set(skill_lower.split())
    for ref_skill, age in SKILL_AGE_MAP.items():
        ref_words = set(ref_skill.lower().split())
        common = skill_words & ref_words
        if len(common) >= 4:  # At least 4 words in common
            return age

    return ""  # Return empty string if no match (will be filled by subdomain grouping)


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

        # Parse PDF
        pdf_data = parse_bdi3_pdf(file)

        # Generate HTML tables with font size and optional summaries
        html_tables = generate_html_tables(pdf_data, font_size, include_summaries)

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
                age = find_age_range(skill_data['skill'])
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

