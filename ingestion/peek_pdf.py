import pdfplumber

with pdfplumber.open('data/election_2025.pdf') as pdf:
    print(f'Total pages: {len(pdf.pages)}')
    page = pdf.pages[0]
    print('Words:', page.extract_words()[:20])
    print('Text:', page.extract_text())
