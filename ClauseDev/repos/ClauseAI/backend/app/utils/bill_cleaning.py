import re

def clean_bill_text(text, preserve_brackets=True, aggressive=False):
    STRUCTURAL_STARTS = (
        'SECTION', 'SEC.', 'CHAPTER', 'Bill ', 'Assembly Bill', 'Senate Bill',
        'An act', 'Approved', 'Filed', 'LEGISLATIVE', 'AB ', 'SB ',
        'Vote:', 'Appropriation:', 'Fiscal Committee:', 'Local Program:',
        'The people', 'Digest Key', 'DIGEST', 'Bill Text'
    )
    ENDING_PUNCTUATION = ('.', ':', ';', ')', ']', '?', '!')

    if not text:
        return "\n"

    if not preserve_brackets:
        text = re.sub(r'\[.*?\]', '', text)

    def clean_line(line):
        line = line.replace('\t', ' ')
        line = re.sub(r' {2,}', ' ', line)
        return line.strip()

    def should_join(current_line, next_line):
        if not current_line or not next_line:
            return False
        if any(next_line.startswith(p) for p in STRUCTURAL_STARTS):
            return False
        if (
            re.match(r'^\d+\.', next_line) or
            re.match(r'^\([a-z0-9]+\)', next_line) or
            re.match(r'^[A-Z]+\s+\d+', next_line)
        ):
            return False
        if current_line.endswith(ENDING_PUNCTUATION):
            if aggressive and current_line.endswith('.'):
                words = current_line.split()
                if words and len(words[-1]) <= 5 and words[-1].count('.') > 1:
                    return True
            return False
        if re.search(r'Section \d+(\.\d+)*$', current_line):
            return False
        return True

    lines = [clean_line(l) for l in text.split('\n')]
    result = []
    i = 0
    while i < len(lines):
        current = lines[i]
        if not current:
            result.append(current)
            i += 1
            continue
        while i + 1 < len(lines) and should_join(current, lines[i + 1]):
            current = current + ' ' + lines[i + 1]
            i += 1
        result.append(current)
        i += 1

    text = '\n'.join(result)
    text = text.replace('. ', '.\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = '\n'.join(l.rstrip() for l in text.split('\n'))
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\s+([.,;:)])', r'\1', text)
    text = re.sub(r'([(\[])\s+', r'\1', text)

    return text.strip() + '\n'