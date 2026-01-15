# BDI-3 PDF to Word Converter

A web application that converts BDI-3 (Battelle Developmental Inventory, 3rd Edition) Family Report PDFs into formatted Word documents.

## Features

- 📤 Simple drag-and-drop or click-to-upload interface
- 📄 Parses BDI-3 Family Report PDFs (pages 4-13: Item Level Scores)
- 📊 Extracts domain, subdomain, skill descriptions, and mastery status
- 📝 Generates formatted Word documents with tables for each domain
- ✅ Marks skills as Mastered, Emerging, or Future Learning Objective
- 🎯 Includes age ranges for skill development

## Domains Covered

- **Adaptive**: Self-Care, Personal Responsibility
- **Social-Emotional**: Self, Social Interactions and Relationships
- **Motor**: Gross Motor, Fine Motor
- **Cognitive**: Attention and Memory, Reasoning and Academic Skills

## Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Mama_PDF_parser
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Open in browser**
   Navigate to `http://localhost:5000`

### Docker Deployment

1. **Build the Docker image**
   ```bash
   docker build -t bdi3-converter .
   ```

2. **Run the container**
   ```bash
   docker run -p 5000:5000 bdi3-converter
   ```

3. **Access the application**
   Navigate to `http://localhost:5000`

## Deployment Options

### Railway

1. Create a new project on [Railway](https://railway.app)
2. Connect your GitHub repository
3. Railway will auto-detect the Dockerfile and deploy

### Render

1. Create a new Web Service on [Render](https://render.com)
2. Connect your GitHub repository
3. Select "Docker" as the environment
4. Deploy

### Vercel (with Python runtime)

1. Install Vercel CLI: `npm i -g vercel`
2. Run `vercel` in the project directory
3. Follow the prompts

## Usage

1. **Upload PDF**: Click the upload area or drag and drop your BDI-3 Family Report PDF
2. **Convert**: Click the "Convert to Word Document" button
3. **Download**: The formatted Word document will automatically download

## Output Format

The generated Word document contains:

- **Title**: BDI-3 Developmental Assessment Report
- **Tables**: One table per domain (Adaptive, Social-Emotional, Motor, Cognitive)
- **Columns**:
  - Average age skills develop
  - Domain: Subdomain / Skill
  - Mastered (X marks)
  - Emerging (X marks)
  - Future Learning Objective (X marks)

## Technical Stack

- **Backend**: Python Flask
- **PDF Parsing**: pdfplumber
- **Word Generation**: python-docx
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: Docker, Gunicorn

## Requirements

- Python 3.11+
- Flask 3.0.0
- pdfplumber 0.11.0
- python-docx 1.1.0

## License

MIT License

## Support

For issues or questions, please open an issue on GitHub.

