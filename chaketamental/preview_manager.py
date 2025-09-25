import xml.etree.ElementTree as ET

def generate_preview(tree):
    if tree is None:
        return ""
    return ET.tostring(tree.getroot(), encoding="unicode")
