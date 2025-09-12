def guardartxt(xml, salida_txt):
    with open(salida_txt, "w", encoding="utf-8") as f:
        f.write(xml)
