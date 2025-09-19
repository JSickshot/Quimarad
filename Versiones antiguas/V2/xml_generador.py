def generar_xml(folio, referencia, observacion):
    xml = (
        "<cfdi:Addenda>\n"
        "    <Tickets>\n"
        f'        <Ticket Folio="{folio}" Referencia="{referencia}" Observacion="{observacion}"/>\n'
        "    </Tickets>\n"
        "</cfdi:Addenda>"
    )
    return xml
