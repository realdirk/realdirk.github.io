#!/usr/bin/env python3
"""Generate Quarto publications from references.bib, without modifying source titles."""
from pathlib import Path
import argparse, re, unicodedata

GROUPS=[('Journal articles','journal'),('Conference proceedings','conference'),('Book chapters','chapter'),('Book reviews','review'),('Conference abstracts','abstract'),('Dissertation','thesis')]

def tex(s):
    accents=[(r'\"u','ü'),(r'\"U','Ü'),(r'\"o','ö'),(r'\"a','ä'),(r"\'c",'ć'),(r"\'e",'é'),(r'\ss','ß')]
    for a,b in accents:
        s=s.replace('{'+a+'}',b).replace(a,b)
    s=re.sub(r'\\(?:textit|emph)\{([^{}]*)\}',r'\1',s)
    return s.replace('---','–').replace('--','–').replace('\\&','&').replace('{','').replace('}','').strip()

def parse(path):
    data=Path(path).read_text(encoding='utf-8'); entries=[]
    for match in re.finditer(r'(?m)^@(\w+)\s*\{\s*([^,]+),',data):
        pos=match.end(); start=pos; depth=1
        while pos<len(data) and depth:
            if data[pos]=='{':depth+=1
            elif data[pos]=='}':depth-=1
            pos+=1
        body=data[start:pos-1]; fields={}
        for m in re.finditer(r'(?m)^\s*([A-Za-z][\w-]*)\s*=\s*',body):
            k=m.group(1).lower(); i=m.end()
            if i>=len(body):continue
            if body[i]=='{':
                j=i+1; level=1
                while j<len(body) and level:
                    if body[j]=='{':level+=1
                    elif body[j]=='}':level-=1
                    j+=1
                fields[k]=body[i+1:j-1].strip()
            elif body[i]=='"':
                j=body.find('"',i+1);fields[k]=body[i+1:j]
            else:fields[k]=body[i:].split(',',1)[0].strip()
        entries.append(dict(type=match.group(1).lower(),key=match.group(2).strip(),**fields))
    return entries

def group(e):
    kw=e.get('keywords','').lower();note=e.get('note','').lower()
    if 'book-review' in kw:return 'review'
    if 'conference-abstract' in kw or 'bulletin of the american physical society' in note:return 'abstract'
    if e['type'] in ('phdthesis','thesis','mastersthesis'):return 'thesis'
    if e['type']=='incollection':return 'chapter'
    if e['type'] in ('inproceedings','conference'):return 'conference'
    return 'journal'

def year(e):
    m=re.search(r'\b(?:19|20)\d{2}\b',e.get('date') or e.get('year') or '')
    return int(m.group()) if m else 0

def initials(given):
    """Compact initials; avoid doubling already abbreviated initials."""
    given=tex(given).strip(); tokens=re.findall(r"[\wÀ-ÿ]+(?:[-’'][\wÀ-ÿ]+)*\.?",given)
    parts=[]
    for tok in tokens:
        if '-' in tok:
            parts.append('-'.join(t[0].upper()+'.' for t in tok.split('-') if t))
        else:parts.append(tok[0].upper()+'.')
    return ' '.join(parts)

def person_display(p):
    p=tex(p).strip()
    if ',' in p:
        family,given=p.split(',',1)
        return initials(given)+' '+family.strip()
    bits=p.split()
    if len(bits)<2:return p
    return initials(' '.join(bits[:-1]))+' '+bits[-1]

def join_people(names):
    if not names:return ''
    if len(names)==1:return names[0]
    if len(names)==2:return ' and '.join(names)
    return ', '.join(names[:-1])+', and '+names[-1]

def note_parts(e):
    note=tex(e.get('note',''))
    if '. In:' in note:return note.split('. In:',1)
    return '',note

def authors(e):
    if e.get('author'):return join_people([person_display(p) for p in re.split(r'\s+and\s+',e['author'])])
    a,_=note_parts(e)
    if not a:return ''
    # The provisional note fields use initials and surnames. Preserve these, fix known typo.
    a=a.replace('D. M. M. Luchtenburg','D. M. Luchtenburg').replace('McLauglin','McLaughlin')
    return a

def sentence_case(title):
    """Sentence case for display, with explicit engineering notation protection."""
    t=tex(title)
    # Protect technical strings before lowercasing; do not edit the .bib title.
    protected = re.compile(r'(?<![\w])(?:SO\(3\)|SE\(3\)|2-D|3-D|2D|3D|D-shaped|Re(?=\s*=)|POD|AIAA|IEEE|ASME|MRI|NOx|MATLAB|ROV|DMD|CFD|ICRA|AAS|APS|NASA|PIV)(?![\w])',re.I)
    stash=[]
    def save(m):
        w=m.group(0)
        fixes={'so(3)':'SO(3)','se(3)':'SE(3)','2-d':'2-D','3-d':'3-D',
               '2d':'2D','3d':'3D','d-shaped':'D-shaped','re':'Re','nox':'NOx'}
        stash.append(fixes.get(w.lower(),w.upper() if w.lower() in {'pod','aiaa','ieee','asme','mri','matlab','rov','dmd','cfd','icra','aas','aps','nasa','piv'} else w))
        return f'@@{len(stash)-1}@@'
    t=protected.sub(save,t)
    # Convert only mixed-case and title-case words; protected tokens are restored.
    t=re.sub(r'[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ’\'-]*',lambda m:m.group().lower(),t)
    t=re.sub(r'(^\s*|:\s+)([a-zà-ÿ])',lambda m:m.group(1)+m.group(2).upper(),t)
    for i,w in enumerate(stash):t=t.replace(f'@@{i}@@',w)
    # Known proper-name exception in this corpus.
    t=re.sub(r'\bgalerkin\b','Galerkin',t,flags=re.I)
    t=re.sub(r'\breynolds\b','Reynolds',t,flags=re.I)
    t=re.sub(r'\bbrunton\b','Brunton',t,flags=re.I)
    t=re.sub(r'\bkutz\b','Kutz',t,flags=re.I)
    t=re.sub(r'\[bookshelf\]','[Bookshelf]',t,flags=re.I)
    return t

def markdown_escape(s):
    return s.replace('\\','\\\\').replace('[',r'\[').replace(']',r'\]').replace('*',r'\*')

def clean_note_venue(e):
    """Turn provisional CV note citations into clean, non-duplicated venue text."""
    _, raw=note_parts(e)
    raw=re.sub(r'\s+', ' ', raw).strip().strip('*').strip()
    raw=re.sub(r'\s*\(?'+re.escape(str(year(e)))+r'\)?\.\s*$', '', raw) if year(e) else raw
    raw=raw.rstrip(' .;')
    # Correct obvious repeated year, without touching conference dates in prose.
    if year(e):
        raw=re.sub(r'\.\s*'+str(year(e))+r'\s*$', '',raw).rstrip(' .')
    return raw

def venue(e):
    g=group(e)
    if g=='thesis':
        school=e.get('school') or e.get('institution')
        return ', '.join(filter(None,['Ph.D. dissertation',tex(school) if school else '',str(year(e)) if year(e) else '']))+'.'
    source=e.get('journaltitle') or e.get('journal') or e.get('booktitle')
    if not source:
        raw=clean_note_venue(e)
        if not raw:return ''
        # Preserve descriptive dates and identifiers, but append the year only once.
        return raw + ('' if re.search(r'\b'+str(year(e))+r'\b',raw) else ', '+str(year(e))) + '.'
    v=tex(source); details=[]
    if e.get('volume') and g in ('journal','review','abstract','chapter'):
        details.append('vol. '+tex(e['volume']))
    if e.get('number') and g in ('journal','review','abstract'):
        details.append('no. '+tex(e['number']))
    if g=='conference':
        n=e.get('note','')
        match=re.search(r'(?:ASME paper|Paper)\s+(IMECE\d{4}-\d+|DSCC\d{4}-\d+)',n,re.I)
        if match:details.append('paper '+match.group(1))
        elif e.get('doi') and re.search(r'10\.1115/(IMECE\d{4}-\d+|DSCC\d{4}-\d+)',e['doi'],re.I):
            details.append('paper '+e['doi'].split('/')[-1])
    if e.get('pages'):
        pg=tex(e['pages']); first,last=(pg.split('–',1)+[''])[:2]
        if last and first==last:pg=first
        details.append(('pp. ' if '–' in pg else 'p. ')+pg)
    elif e.get('eid'):details.append('article '+tex(e['eid']))
    if year(e):
        # Proceedings title may already encode conference year; publication year still matters.
        details.append(str(year(e)))
    return v+(', '+', '.join(details) if details else '')+'.'

def title(e):
    label=markdown_escape(sentence_case(e.get('title','Untitled')))
    doi=e.get('doi','').strip();url='https://doi.org/'+doi if doi else e.get('url','').strip()
    return '['+label+']('+url+')' if url else label

def generate(entries):
    out=['---','title: "Publications"','title-block-banner: false','page-layout: full','toc: false','---','','::: {.publications-container}','','Publications are listed in reverse chronological order within each category. Titles link to publisher records where available. See my [Google Scholar profile](https://scholar.google.com/citations?user=s7vf-rcAAAAJ) for citation metrics.','']
    for heading,g in GROUPS:
        records=sorted((e for e in entries if group(e)==g),key=lambda e:(-year(e),e.get('title','').casefold()))
        if not records:continue
        out+=['## '+heading,'']
        for e in records:
            out+=['::: {.publication}','','### '+title(e),'']
            if authors(e):out+=[authors(e),'']
            if venue(e):out+=['*'+markdown_escape(venue(e))+'*','']
            if e.get('eprinttype','').lower()=='arxiv' and e.get('eprint'):
                out+=['[Open-access preprint](https://arxiv.org/abs/'+e['eprint']+')','']
            m=re.search(r'Open-access copy:\s*(https?://\S+)',e.get('note',''))
            if m:out+=['[Open-access full text]('+m.group(1).rstrip('.,')+')','']
            out+=[':::','']
    return '\n'.join(out+[':::',''])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bib',default='references.bib');p.add_argument('--output',default='publications.qmd');a=p.parse_args()
    entries=parse(a.bib);Path(a.output).write_text(generate(entries),encoding='utf8')
    from collections import Counter
    print('Generated',a.output,'from',len(entries),'records:',dict(Counter(group(e) for e in entries)))
    print('DOI-linked titles:',sum(bool(e.get('doi')) for e in entries))
