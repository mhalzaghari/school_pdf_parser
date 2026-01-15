# Usage Guide

## How to Use the BDI-3 PDF to Word Converter

### Step 1: Access the Application

**Local Development:**
```bash
python3 app.py
```
Then open: `http://localhost:8080`

**Production:**
Visit your deployed URL (e.g., `https://your-app.railway.app`)

---

### Step 2: Upload Your BDI-3 PDF

1. **Click the upload area** or **drag and drop** your PDF file
2. The file must be a **BDI-3 Family Report PDF**
3. Supported format: `.pdf` only

**What the app looks for:**
- Pages 4-13: "Item Level Scores" section
- Three-column format: `DOMAIN: SUBDOMAIN | SKILL | MASTERY`

---

### Step 3: Convert

1. Click the **"Convert to Word Document"** button
2. Wait for processing (usually 5-10 seconds)
3. The Word document will automatically download

---

### Step 4: Review the Output

The generated Word document contains:

**Title:** BDI-3 Developmental Assessment Report

**Four Tables (one per domain):**

1. **Adaptive**
   - Self-Care
   - Personal Responsibility

2. **Social-Emotional**
   - Self
   - Social Interactions and Relationships

3. **Motor**
   - Gross Motor
   - Fine Motor

4. **Cognitive**
   - Attention and Memory
   - Reasoning and Academic Skills

**Table Format:**

| Average age skills develop | Domain: Subdomain / Skill | Mastered | Emerging | Future Learning Objective |
|----------------------------|---------------------------|----------|----------|---------------------------|
| (2 yrs) | **Adaptive: Self-Care** | | | |
| (2 yrs) | Washes his or her hands | X | | |
| (3 yrs) | Shows signs of pretoileting readiness | | | X |
| (2 yrs) | **Adaptive: Personal Responsibility** | | | |
| (4 yrs) | Uses appropriate behavior in public | X | | |

---

## Expected PDF Format

The BDI-3 Family Report PDF should contain:

### Pages 4-13: Item Level Scores

Example format:
```
ADAPTIVE: SELF-CARE
Communicates the need or desire for food          MASTERED
Washes his or her hands                           MASTERED
Shows signs of pretoileting readiness             FUTURE LEARNING OBJECTIVE

ADAPTIVE: PERSONAL RESPONSIBILITY
Follows simple rules                              EMERGING
Uses appropriate behavior in public               MASTERED
```

### Mastery Status Keywords

The parser looks for these keywords:
- `MASTERED` → Marks "X" in Mastered column
- `EMERGING` → Marks "X" in Emerging column
- `FUTURE LEARNING OBJECTIVE` or `FUTURE` → Marks "X" in Future Learning Objective column

---

## Age Range Mapping

The app includes a reference database of skills and their typical development ages:

**Examples:**
- "Washes his or her hands" → (2 yrs)
- "Shows signs of pretoileting readiness" → (3 yrs)
- "Uses the toilet" → (4 yrs)
- "Dresses self completely" → (5 yrs)

If a skill is not in the reference database, it will show `(Unknown)`.

---

## Customizing Age Ranges

To add or modify age ranges, edit `app.py`:

```python
AGE_RANGES = {
    "Your skill description": "(age range)",
    "Washes his or her hands": "(2 yrs)",
    # Add more mappings here
}
```

Then redeploy the application.

---

## Troubleshooting

### "No file uploaded" error
- Make sure you selected a file before clicking Convert
- Check that the file is a PDF

### "File must be a PDF" error
- Only `.pdf` files are accepted
- Rename your file to have a `.pdf` extension

### Empty or incomplete Word document
- Verify your PDF contains pages 4-13 with Item Level Scores
- Check that the PDF format matches the expected three-column layout
- Ensure the PDF is not password-protected or corrupted

### Skills showing "(Unknown)" age
- The skill is not in the reference database
- You can add it manually to `AGE_RANGES` in `app.py`

### Conversion takes too long
- Large PDFs may take 10-20 seconds
- If it takes longer than 30 seconds, refresh and try again
- Check your internet connection (for deployed versions)

---

## Tips for Best Results

1. **Use official BDI-3 Family Report PDFs** - The parser is designed for this specific format
2. **Check page numbers** - Ensure pages 4-13 contain the Item Level Scores
3. **Verify mastery keywords** - Make sure the PDF uses standard keywords (MASTERED, EMERGING, FUTURE)
4. **Review the output** - Always check the generated Word document for accuracy
5. **Customize as needed** - Edit the Word document after generation if needed

---

## Example Workflow

**Scenario:** You have a BDI-3 assessment for a 3-year-old child.

1. **Upload** the BDI-3 Family Report PDF
2. **Convert** to Word document
3. **Review** the generated tables
4. **Share** the Word document with parents, therapists, or educators
5. **Use** the document for IEP planning, progress tracking, or goal setting

---

## Privacy & Security

- ✅ **No data is stored** - PDFs are processed in memory only
- ✅ **No user accounts** - No login or registration required
- ✅ **No tracking** - No analytics or cookies
- ✅ **Secure processing** - All processing happens server-side
- ✅ **Immediate deletion** - Files are deleted after conversion

---

## Support

For issues or questions:
1. Check this usage guide
2. Review the README.md
3. Check the deployment logs
4. Open an issue on GitHub

---

## Advanced Usage

### API Endpoint

You can also use the API directly:

```bash
curl -X POST http://localhost:8080/convert \
  -F "file=@/path/to/your/bdi3.pdf" \
  --output report.docx
```

**Response:**
- Success: Word document file (`.docx`)
- Error: JSON with error message

### Batch Processing

To convert multiple PDFs:

```bash
for pdf in *.pdf; do
  curl -X POST http://localhost:8080/convert \
    -F "file=@$pdf" \
    --output "${pdf%.pdf}.docx"
done
```

---

## Next Steps

- Deploy to Railway, Render, or Fly.io (see DEPLOYMENT.md)
- Share the URL with your friend
- Customize age ranges as needed
- Add more domains or subdomains if required

