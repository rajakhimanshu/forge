import zipfile
import xml.etree.ElementTree as ET

def extract_docx_text(path):
    document = zipfile.ZipFile(path)
    xml_content = document.read('word/document.xml')
    document.close()
    
    tree = ET.fromstring(xml_content)
    namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    texts = []
    for paragraph in tree.findall('.//w:p', namespace):
        p_text = []
        for run in paragraph.findall('.//w:t', namespace):
            if run.text:
                p_text.append(run.text)
        if p_text:
            texts.append("".join(p_text))
            
    return "\n".join(texts)

if __name__ == "__main__":
    print(extract_docx_text('forge_devguide_deep_audit.docx'))
