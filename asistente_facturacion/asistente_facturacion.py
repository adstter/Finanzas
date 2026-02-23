# -*- coding: utf-8 -*-
"""
Asistente de Facturacion ADSTTER
Certifica facturas de Zoho Books con INFILE (FEL Guatemala)
"""

import json
import requests
import os
import sys
import tempfile
from datetime import datetime
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Configuracion de consola para Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.json')

def cargar_config():
    """Carga la configuracion desde el archivo JSON"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def obtener_access_token(config):
    """Obtiene un nuevo access token usando el refresh token"""
    url = "https://accounts.zoho.com/oauth/v2/token"
    data = {
        "refresh_token": config['zoho']['refresh_token'],
        "client_id": config['zoho']['client_id'],
        "client_secret": config['zoho']['client_secret'],
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        print(f"Error al obtener token: {response.text}")
        return None

def obtener_facturas_borrador(config, access_token):
    """Obtiene las facturas en estado borrador de Zoho Books"""
    org_id = config['zoho']['organization_id']
    url = f"{config['zoho']['api_domain']}/books/v3/invoices"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {
        "organization_id": org_id,
        "status": "draft"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('invoices', [])
    else:
        print(f"Error al obtener facturas: {response.text}")
        return []

def obtener_detalle_factura(config, access_token, invoice_id):
    """Obtiene el detalle completo de una factura"""
    org_id = config['zoho']['organization_id']
    url = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {"organization_id": org_id}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('invoice', {})
    else:
        print(f"Error al obtener detalle de factura: {response.text}")
        return None

def obtener_contacto(config, access_token, contact_id):
    """Obtiene los datos de un contacto"""
    org_id = config['zoho']['organization_id']
    url = f"{config['zoho']['api_domain']}/books/v3/contacts/{contact_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {"organization_id": org_id}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('contact', {})
    else:
        return None

def generar_xml_factura(config, factura, contacto):
    """Genera el XML FEL para certificacion en INFILE"""
    emisor = config['emisor']
    frases = config['frases']

    # Datos del receptor (cliente)
    # SIEMPRE buscar primero en campos personalizados (tienen prioridad)
    nit_receptor = ''
    custom_fields = contacto.get('custom_fields', [])
    # Debug: mostrar campos personalizados disponibles
    if custom_fields:
        print(f"   [DEBUG] Campos personalizados: {[cf.get('label', '') for cf in custom_fields]}")
    for cf in custom_fields:
        label = cf.get('label', '').upper().strip()
        # Buscar cualquier campo que contenga "NIT" o sea identificador fiscal
        # Incluye "ID DE EMPRESA" que es donde Zoho guarda el NIT
        if 'NIT' in label or 'ID DE EMPRESA' in label or label in ['TAX ID', 'TAX NUMBER', 'NUMERO FISCAL', 'ID FISCAL', 'RFC', 'RUC', 'RUT', 'ID EMPRESA']:
            nit_receptor = cf.get('value', '') or ''
            if nit_receptor and nit_receptor.upper() not in ['N/A', 'CF', '']:
                print(f"   [DEBUG] NIT encontrado en campo '{cf.get('label')}': {nit_receptor}")
                break

    # Si no hay NIT en campos personalizados, usar tax_number como fallback
    if not nit_receptor or nit_receptor.upper() in ['N/A', 'CF', '']:
        nit_receptor = contacto.get('tax_number', '') or ''

    # Limpiar NIT - solo numeros, letras y guion
    nit_receptor = ''.join(c for c in str(nit_receptor) if c.isalnum() or c == '-')
    # Si esta vacio o es consumidor final
    if not nit_receptor or nit_receptor.upper() in ['CF', 'C/F', 'CONSUMIDORFINAL', 'CONSUMIDOR FINAL', 'N/A']:
        nit_receptor = 'CF'
    # Convertir a mayusculas
    nit_receptor = nit_receptor.upper()

    # Buscar nombre a facturar en campos personalizados, si no usar contact_name
    nombre_receptor = ''
    custom_fields = contacto.get('custom_fields', [])
    for cf in custom_fields:
        label = cf.get('label', '').upper()
        if label in ['NOMBRE A FACTURAR', 'RAZON SOCIAL', 'NOMBRE FISCAL']:
            nombre_receptor = cf.get('value', '') or ''
            break

    if not nombre_receptor:
        nombre_receptor = contacto.get('contact_name') or 'Consumidor Final'
    email_receptor = contacto.get('email', '') or ''
    direccion_receptor = contacto.get('billing_address', {}) or {}

    # Fecha y hora actual
    fecha_emision = datetime.now().strftime('%Y-%m-%dT%H:%M:%S-06:00')

    # Moneda
    moneda = factura.get('currency_code', 'GTQ')

    # Crear XML
    ns = "http://www.sat.gob.gt/dte/fel/0.2.0"
    ns_map = {
        'dte': ns,
        'xsi': "http://www.w3.org/2001/XMLSchema-instance"
    }

    # Detectar si es exportacion (pais diferente de Guatemala)
    # Si el país está vacío o no definido, asumir que es LOCAL (Guatemala)
    pais_cliente = direccion_receptor.get('country', '') or ''
    pais_cliente = pais_cliente.strip().lower()

    # Lista de valores que indican Guatemala o local
    paises_locales = ['guatemala', 'gt', 'gua', '']
    es_exportacion = pais_cliente not in paises_locales

    # Construir XML como string para mayor control
    xml_lines = []
    xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_lines.append(f'<dte:GTDocumento xmlns:dte="{ns}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" Version="0.1">')
    xml_lines.append('  <dte:SAT ClaseDocumento="dte">')
    xml_lines.append('    <dte:DTE ID="DatosCertificados">')
    xml_lines.append(f'      <dte:DatosEmision ID="DatosEmision">')

    # Datos Generales - FACT para local, FACT para exportacion de servicios
    tipo_doc = "FACT"
    # Para exportacion se agrega atributo Exp
    if es_exportacion:
        xml_lines.append(f'        <dte:DatosGenerales CodigoMoneda="{moneda}" Exp="SI" FechaHoraEmision="{fecha_emision}" Tipo="{tipo_doc}"/>')
    else:
        xml_lines.append(f'        <dte:DatosGenerales CodigoMoneda="{moneda}" FechaHoraEmision="{fecha_emision}" Tipo="{tipo_doc}"/>')

    # Emisor
    xml_lines.append(f'        <dte:Emisor AfiliacionIVA="{emisor["afiliacion_iva"]}" CodigoEstablecimiento="{emisor["codigo_establecimiento"]}" CorreoEmisor="" NITEmisor="{emisor["nit"]}" NombreComercial="{emisor["nombre_comercial"]}" NombreEmisor="{emisor["nombre"]}">')
    xml_lines.append(f'          <dte:DireccionEmisor>')
    xml_lines.append(f'            <dte:Direccion>{emisor["direccion"]}</dte:Direccion>')
    xml_lines.append(f'            <dte:CodigoPostal>{emisor["codigo_postal"]}</dte:CodigoPostal>')
    xml_lines.append(f'            <dte:Municipio>{emisor["municipio"]}</dte:Municipio>')
    xml_lines.append(f'            <dte:Departamento>{emisor["departamento"]}</dte:Departamento>')
    xml_lines.append(f'            <dte:Pais>{emisor["pais"]}</dte:Pais>')
    xml_lines.append(f'          </dte:DireccionEmisor>')
    xml_lines.append(f'        </dte:Emisor>')

    # Funcion para limpiar texto XML
    def limpiar_xml(texto):
        if not texto:
            return ''
        texto = str(texto)
        texto = texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
        return texto.strip()

    # Codigos de pais ISO validos
    codigos_pais_validos = ['AF', 'AL', 'DE', 'AD', 'AO', 'AI', 'AQ', 'AG', 'SA', 'DZ', 'AR', 'AM', 'AW', 'AU', 'AT', 'AZ', 'BS', 'BD', 'BB', 'BH', 'BE', 'BZ', 'BJ', 'BM', 'BY', 'BO', 'BA', 'BW', 'BR', 'BN', 'BG', 'BF', 'BI', 'BT', 'CV', 'KH', 'CM', 'CA', 'QA', 'TD', 'CL', 'CN', 'CY', 'CO', 'KM', 'KP', 'KR', 'CR', 'CI', 'HR', 'CU', 'CW', 'DK', 'DM', 'EC', 'EG', 'SV', 'AE', 'ER', 'SK', 'SI', 'ES', 'US', 'EE', 'ET', 'PH', 'FI', 'FJ', 'FR', 'GA', 'GM', 'GE', 'GH', 'GI', 'GD', 'GR', 'GL', 'GP', 'GU', 'GT', 'GF', 'GG', 'GN', 'GQ', 'GW', 'GY', 'HT', 'HN', 'HK', 'HU', 'IN', 'ID', 'IQ', 'IR', 'IE', 'IS', 'IL', 'IT', 'JM', 'JP', 'JE', 'JO', 'KZ', 'KE', 'KG', 'KI', 'KW', 'LA', 'LS', 'LV', 'LB', 'LR', 'LY', 'LI', 'LT', 'LU', 'MO', 'MK', 'MG', 'MY', 'MW', 'MV', 'ML', 'MT', 'MA', 'MQ', 'MU', 'MR', 'MX', 'FM', 'MD', 'MC', 'MN', 'ME', 'MS', 'MZ', 'MM', 'NA', 'NR', 'NP', 'NI', 'NE', 'NG', 'NO', 'NC', 'NZ', 'OM', 'NL', 'PK', 'PW', 'PS', 'PA', 'PG', 'PY', 'PE', 'PF', 'PL', 'PT', 'PR', 'GB', 'CF', 'CZ', 'CG', 'CD', 'DO', 'RE', 'RW', 'RO', 'RU', 'EH', 'WS', 'AS', 'BL', 'KN', 'SM', 'MF', 'PM', 'VC', 'SH', 'LC', 'ST', 'SN', 'RS', 'SC', 'SL', 'SG', 'SX', 'SY', 'SO', 'LK', 'SZ', 'ZA', 'SD', 'SS', 'SE', 'CH', 'SR', 'TH', 'TW', 'TZ', 'TJ', 'IO', 'TF', 'TL', 'TG', 'TK', 'TO', 'TT', 'TN', 'TM', 'TR', 'TV', 'UA', 'UG', 'UY', 'UZ', 'VU', 'VA', 'VE', 'VN', 'WF', 'YE', 'DJ', 'ZM', 'ZW']

    # Receptor - limpiar todos los campos
    dir_receptor = limpiar_xml(direccion_receptor.get('address', '')) or 'Ciudad'
    cp_receptor = direccion_receptor.get('zip', '01001') or '01001'
    mun_receptor = limpiar_xml(direccion_receptor.get('city', '')) or 'Guatemala'
    dep_receptor = limpiar_xml(direccion_receptor.get('state', '')) or 'Guatemala'
    pais_receptor = direccion_receptor.get('country', 'GT') or 'GT'

    # Convertir nombres de pais a codigo ISO
    paises_nombre_a_codigo = {
        'guatemala': 'GT', 'mexico': 'MX', 'estados unidos': 'US', 'usa': 'US', 'united states': 'US',
        'el salvador': 'SV', 'honduras': 'HN', 'nicaragua': 'NI', 'costa rica': 'CR', 'panama': 'PA',
        'colombia': 'CO', 'españa': 'ES', 'spain': 'ES', 'canada': 'CA', 'argentina': 'AR',
        'chile': 'CL', 'peru': 'PE', 'brasil': 'BR', 'brazil': 'BR', 'ecuador': 'EC'
    }

    # Si es nombre de pais, convertir a codigo
    if pais_receptor.lower() in paises_nombre_a_codigo:
        pais_receptor = paises_nombre_a_codigo[pais_receptor.lower()]

    # Si no es un codigo valido, usar GT por defecto
    pais_receptor = pais_receptor.upper()
    if pais_receptor not in codigos_pais_validos:
        pais_receptor = 'GT'

    # Limpiar nombre del receptor
    nombre_receptor = limpiar_xml(nombre_receptor)
    if not nombre_receptor:
        nombre_receptor = 'Consumidor Final'

    # Para exportaciones, el ID del receptor debe ser "CF" según normativa SAT
    id_receptor = "CF" if es_exportacion else nit_receptor
    xml_lines.append(f'        <dte:Receptor CorreoReceptor="{email_receptor}" IDReceptor="{id_receptor}" NombreReceptor="{nombre_receptor}">')
    xml_lines.append(f'          <dte:DireccionReceptor>')
    xml_lines.append(f'            <dte:Direccion>{dir_receptor}</dte:Direccion>')
    xml_lines.append(f'            <dte:CodigoPostal>{cp_receptor}</dte:CodigoPostal>')
    xml_lines.append(f'            <dte:Municipio>{mun_receptor}</dte:Municipio>')
    xml_lines.append(f'            <dte:Departamento>{dep_receptor}</dte:Departamento>')
    xml_lines.append(f'            <dte:Pais>{pais_receptor}</dte:Pais>')
    xml_lines.append(f'          </dte:DireccionReceptor>')
    xml_lines.append(f'        </dte:Receptor>')

    # Frases
    xml_lines.append('        <dte:Frases>')
    if es_exportacion:
        # Para exportaciones: Frase tipo 4 (Exento o no afecto al IVA) es obligatoria
        xml_lines.append('          <dte:Frase CodigoEscenario="1" TipoFrase="4"/>')
    else:
        # Frases normales para ventas locales
        for frase in frases:
            xml_lines.append(f'          <dte:Frase CodigoEscenario="{frase["codigo_escenario"]}" TipoFrase="{frase["tipo_frase"]}"/>')
    xml_lines.append('        </dte:Frases>')

    # Items
    xml_lines.append('        <dte:Items>')
    line_items = factura.get('line_items', [])
    total_iva_calculado = 0
    gran_total_calculado = 0

    for i, item in enumerate(line_items, 1):
        cantidad = float(item.get('quantity', 1))
        # rate en Zoho es el precio SIN IVA
        precio_sin_iva = float(item.get('rate', 0))
        descuento = float(item.get('discount_amount', 0) or 0)

        # Combinar nombre del producto + descripcion
        nombre_producto = item.get('name', '') or ''
        descripcion_adicional = item.get('description', '') or ''

        # Crear descripcion completa: "Nombre - Descripcion" o solo uno si el otro esta vacio
        if nombre_producto and descripcion_adicional:
            descripcion = f"{nombre_producto} - {descripcion_adicional}"
        else:
            descripcion = nombre_producto or descripcion_adicional or 'Servicio'

        descripcion = limpiar_xml(descripcion)

        # Calcular montos - diferente para exportacion vs local
        if es_exportacion:
            # EXPORTACION: Sin IVA
            precio_unitario = precio_sin_iva
            precio_total = cantidad * precio_unitario
            monto_gravable = (cantidad * precio_sin_iva) - descuento
            monto_impuesto = 0  # Sin IVA para exportaciones
            total_linea = monto_gravable
            codigo_unidad_gravable = "2"  # 2 = Exento
        else:
            # LOCAL: Con IVA 12%
            precio_unitario_con_iva = precio_sin_iva * 1.12
            precio_total = cantidad * precio_unitario_con_iva
            monto_gravable = (cantidad * precio_sin_iva) - descuento
            monto_impuesto = monto_gravable * 0.12
            total_linea = monto_gravable + monto_impuesto
            precio_unitario = precio_unitario_con_iva
            codigo_unidad_gravable = "1"  # 1 = Gravado

        total_iva_calculado += monto_impuesto
        gran_total_calculado += total_linea

        xml_lines.append(f'          <dte:Item BienOServicio="S" NumeroLinea="{i}">')
        xml_lines.append(f'            <dte:Cantidad>{cantidad:.2f}</dte:Cantidad>')
        xml_lines.append(f'            <dte:UnidadMedida>UND</dte:UnidadMedida>')
        xml_lines.append(f'            <dte:Descripcion>{descripcion}</dte:Descripcion>')
        xml_lines.append(f'            <dte:PrecioUnitario>{precio_unitario:.6f}</dte:PrecioUnitario>')
        xml_lines.append(f'            <dte:Precio>{precio_total:.6f}</dte:Precio>')
        xml_lines.append(f'            <dte:Descuento>{descuento:.6f}</dte:Descuento>')
        xml_lines.append('            <dte:Impuestos>')
        xml_lines.append('              <dte:Impuesto>')
        xml_lines.append(f'                <dte:NombreCorto>IVA</dte:NombreCorto>')
        xml_lines.append(f'                <dte:CodigoUnidadGravable>{codigo_unidad_gravable}</dte:CodigoUnidadGravable>')
        xml_lines.append(f'                <dte:MontoGravable>{monto_gravable:.6f}</dte:MontoGravable>')
        xml_lines.append(f'                <dte:MontoImpuesto>{monto_impuesto:.6f}</dte:MontoImpuesto>')
        xml_lines.append('              </dte:Impuesto>')
        xml_lines.append('            </dte:Impuestos>')
        xml_lines.append(f'            <dte:Total>{total_linea:.6f}</dte:Total>')
        xml_lines.append('          </dte:Item>')
    xml_lines.append('        </dte:Items>')

    # Totales - usar los valores calculados para consistencia
    xml_lines.append('        <dte:Totales>')
    xml_lines.append('          <dte:TotalImpuestos>')
    xml_lines.append(f'            <dte:TotalImpuesto NombreCorto="IVA" TotalMontoImpuesto="{total_iva_calculado:.6f}"/>')
    xml_lines.append('          </dte:TotalImpuestos>')
    xml_lines.append(f'          <dte:GranTotal>{gran_total_calculado:.6f}</dte:GranTotal>')
    xml_lines.append('        </dte:Totales>')

    # Complemento de Exportación (obligatorio para exportaciones)
    if es_exportacion:
        # Namespace del complemento de exportación
        ns_exp = "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0"

        # Datos del comprador/destinatario (usar datos del receptor)
        nombre_comprador = limpiar_xml(nombre_receptor)
        direccion_comprador = f"{dir_receptor}, {mun_receptor}, {dep_receptor}"
        direccion_comprador = limpiar_xml(direccion_comprador)

        xml_lines.append('        <dte:Complementos>')
        xml_lines.append(f'          <dte:Complemento IDComplemento="ID_EXPORTACION" NombreComplemento="Exportacion" URIComplemento="{ns_exp}">')
        xml_lines.append(f'            <cex:Exportacion xmlns:cex="{ns_exp}" Version="1">')
        xml_lines.append(f'              <cex:NombreConsignatarioODestinatario>{nombre_comprador}</cex:NombreConsignatarioODestinatario>')
        xml_lines.append(f'              <cex:DireccionConsignatario>{direccion_comprador}</cex:DireccionConsignatario>')
        xml_lines.append(f'              <cex:NombreComprador>{nombre_comprador}</cex:NombreComprador>')
        xml_lines.append(f'              <cex:DireccionComprador>{direccion_comprador}</cex:DireccionComprador>')
        xml_lines.append(f'              <cex:CodigoComprador>CF</cex:CodigoComprador>')
        xml_lines.append(f'              <cex:NombreExportador>{limpiar_xml(emisor["nombre"])}</cex:NombreExportador>')
        xml_lines.append(f'              <cex:CodigoExportador>{emisor["nit"]}</cex:CodigoExportador>')
        xml_lines.append('            </cex:Exportacion>')
        xml_lines.append('          </dte:Complemento>')
        xml_lines.append('        </dte:Complementos>')

    xml_lines.append('      </dte:DatosEmision>')
    xml_lines.append('    </dte:DTE>')
    xml_lines.append('  </dte:SAT>')
    xml_lines.append('</dte:GTDocumento>')

    return '\n'.join(xml_lines)

def certificar_factura_infile(config, xml_content, identificador):
    """Envia el XML a INFILE para certificacion"""
    infile = config['infile']

    headers = {
        'Content-Type': 'application/xml',
        'UsuarioFirma': infile['usuario_firma'],
        'LlaveFirma': infile['llave_firma'],
        'UsuarioApi': infile['usuario_api'],
        'LlaveApi': infile['llave_api'],
        'identificador': identificador
    }

    response = requests.post(
        infile['url_certificacion'],
        headers=headers,
        data=xml_content.encode('utf-8')
    )

    if response.status_code == 200:
        return response.json()
    else:
        return {
            'resultado': False,
            'descripcion': f'Error HTTP {response.status_code}: {response.text}'
        }

def actualizar_factura_zoho(config, access_token, invoice_id, datos_certificacion, ya_enviada=False):
    """Actualiza la factura en Zoho con los datos de certificacion y cambia el numero de factura"""
    org_id = config['zoho']['organization_id']
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {"organization_id": org_id}

    # Crear nuevo numero de factura con Serie-Numero de INFILE
    serie = datos_certificacion.get('serie', '')
    numero = datos_certificacion.get('numero', '')
    nuevo_numero_factura = f"Serie: {serie} Numero de DTE: {numero}" if serie and numero else None

    # Obtener fecha de certificacion y formatearla para Zoho (YYYY-MM-DD)
    fecha_cert = datos_certificacion.get('fecha', '')
    fecha_zoho = None
    if fecha_cert:
        # La fecha viene como "2025-12-05T10:30:00-06:00", necesitamos solo "2025-12-05"
        try:
            fecha_zoho = fecha_cert.split('T')[0]
        except:
            # Si no hay fecha de certificacion, usar fecha de hoy
            fecha_zoho = datetime.now().strftime('%Y-%m-%d')
    else:
        fecha_zoho = datetime.now().strftime('%Y-%m-%d')

    # Primero marcar como enviada si no lo esta (requerido para poder actualizar algunos campos)
    if not ya_enviada:
        url_status = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}/status/sent"
        resp_status = requests.post(url_status, headers=headers, params=params)
        if resp_status.status_code == 200:
            print("   Factura marcada como enviada para permitir actualizacion...")
        else:
            print(f"   [DEBUG] No se pudo marcar como enviada: {resp_status.status_code}")

    # Ahora actualizar la factura
    url = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}"

    # IMPORTANTE: Zoho requiere "reason" para actualizar facturas enviadas
    uuid_fel = datos_certificacion.get('uuid', '')
    serie = datos_certificacion.get('serie', '')
    numero = datos_certificacion.get('numero', '')
    fecha_cert_completa = datos_certificacion.get('fecha', '')
    url_pdf_infile = datos_certificacion.get('url_pdf_infile', '')
    url_xml_infile = datos_certificacion.get('url_xml_infile', '')

    # Nota para el cliente que aparecerá en el PDF
    nota_cliente = f"NÚMERO DE AUTORIZACIÓN: {uuid_fel}"

    # Campos personalizados FEL que ya existen en Zoho Books (usando label)
    custom_fields = [
        {"label": "fel_uuid", "value": uuid_fel},
        {"label": "fel_serie", "value": serie},
        {"label": "fel_numero", "value": numero},
        {"label": "fel_fecha_certificacion", "value": fecha_cert_completa},
        {"label": "fel_estado", "value": "Certificada"}
    ]

    # Agregar URL del PDF si INFILE lo proporcionó
    if url_pdf_infile:
        custom_fields.append({"label": "fel_url_pdf", "value": url_pdf_infile})

    # Agregar URL del XML si INFILE lo proporcionó
    if url_xml_infile:
        custom_fields.append({"label": "fel_url_xml", "value": url_xml_infile})

    data = {
        "reason": f"Certificacion FEL - UUID: {uuid_fel}",
        "notes": nota_cliente,
        "custom_fields": custom_fields
    }

    # Actualizar el numero de factura si tenemos los datos de INFILE
    if nuevo_numero_factura:
        data["invoice_number"] = nuevo_numero_factura

    # Actualizar la fecha de emision con la fecha de certificacion
    if fecha_zoho:
        data["date"] = fecha_zoho

    response = requests.put(url, headers=headers, params=params, json=data)

    # Debug: mostrar resultado de la actualizacion
    if response.status_code != 200:
        print(f"   [DEBUG] Error al actualizar Zoho: {response.status_code}")
        try:
            resp_json = response.json()
            mensaje = resp_json.get('message', response.text[:200])
            print(f"   [DEBUG] Mensaje: {mensaje}")
        except:
            print(f"   [DEBUG] Respuesta: {response.text[:200]}")
        return False
    else:
        print(f"   Numero actualizado a: {nuevo_numero_factura}")
        print(f"   Fecha actualizada a: {fecha_zoho}")
        return True

def marcar_factura_enviada(config, access_token, invoice_id):
    """Marca la factura como enviada (cambia de borrador a abierta)"""
    org_id = config['zoho']['organization_id']
    url = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}/status/sent"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {"organization_id": org_id}

    response = requests.post(url, headers=headers, params=params)
    return response.status_code == 200

def enviar_factura_email(config, access_token, invoice_id, emails, datos_certificacion=None, contacto=None):
    """Envia la factura por email a los contactos con datos de certificacion"""
    org_id = config['zoho']['organization_id']
    url = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}/email"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {"organization_id": org_id}

    # Obtener nombres del cliente
    nombre_visualizacion = ""
    razon_social = ""

    if contacto:
        # Nombre de visualizacion (como aparece en Zoho)
        nombre_visualizacion = contacto.get('contact_name', '') or ''

        # Buscar razon social en campos personalizados
        custom_fields = contacto.get('custom_fields', [])
        for cf in custom_fields:
            label = cf.get('label', '').upper()
            if label in ['NOMBRE A FACTURAR', 'RAZON SOCIAL', 'NOMBRE FISCAL']:
                razon_social = cf.get('value', '') or ''
                break

        # Si no hay razon social en campos personalizados, usar company_name
        if not razon_social:
            razon_social = contacto.get('company_name', '') or nombre_visualizacion

    # Construir cuerpo del correo con datos de certificacion
    if datos_certificacion:
        serie = datos_certificacion.get('serie', '')
        numero = datos_certificacion.get('numero', '')
        uuid_fel = datos_certificacion.get('uuid', '')
        fecha_cert = datos_certificacion.get('fecha', '')

        # URL del PDF de INFILE
        url_pdf_infile = f"https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid={uuid_fel}"

        body = f"""Estimado cliente,

Adjunto encontrará su Factura Electrónica certificada.

DATOS DEL CLIENTE:
- Nombre: {nombre_visualizacion}
- Razón Social: {razon_social}

DATOS DE CERTIFICACIÓN FEL:
- Serie: {serie}
- Número DTE: {numero}
- No. Autorización (UUID): {uuid_fel}
- Fecha de Certificación: {fecha_cert}

VER/DESCARGAR FACTURA CERTIFICADA:
{url_pdf_infile}

Este documento tiene validez tributaria ante SAT.

Atentamente,
ADSTTER
Proyectos de Tecnología y Comunicaciones, S.A."""
    else:
        body = "Adjunto encontrará su factura electrónica certificada."

    data = {
        "to_mail_ids": emails if isinstance(emails, list) else [emails],
        "subject": f"Factura Electrónica {datos_certificacion.get('serie', '')}-{datos_certificacion.get('numero', '')} - ADSTTER" if datos_certificacion else "Factura Electronica - ADSTTER",
        "body": body
    }

    response = requests.post(url, headers=headers, params=params, json=data)
    return response.status_code == 200

def mostrar_menu_facturas(facturas):
    """Muestra el menu de facturas para seleccionar"""
    print("\n" + "="*70)
    print("      ASISTENTE DE FACTURACION ADSTTER - CERTIFICACION FEL")
    print("="*70)

    if not facturas:
        print("\nNo hay facturas en borrador para procesar.")
        return []

    print(f"\nFacturas en borrador encontradas: {len(facturas)}\n")
    print("-"*70)
    print(f"{'#':<4} {'Numero':<15} {'Cliente':<30} {'Total':<15}")
    print("-"*70)

    for i, factura in enumerate(facturas, 1):
        numero = factura.get('invoice_number', 'N/A')
        cliente = factura.get('customer_name', 'N/A')[:28]
        total = factura.get('total', 0)
        moneda = factura.get('currency_code', 'GTQ')
        print(f"{i:<4} {numero:<15} {cliente:<30} {moneda} {total:>10,.2f}")

    print("-"*70)
    print("\nOpciones:")
    print("  - Ingrese numeros separados por coma (ej: 1,3,5)")
    print("  - Ingrese 'T' para seleccionar todas")
    print("  - Ingrese '0' para salir")
    print("-"*70)

    seleccion = input("\nSeleccione las facturas a certificar: ").strip()

    if seleccion == '0':
        return []

    if seleccion.upper() == 'T':
        return list(range(len(facturas)))

    try:
        indices = [int(x.strip()) - 1 for x in seleccion.split(',')]
        indices = [i for i in indices if 0 <= i < len(facturas)]
        return indices
    except:
        print("Seleccion invalida.")
        return []

def descargar_y_adjuntar_pdf_fel(config, access_token, invoice_id, url_pdf, serie, numero):
    """Descarga el PDF de INFILE y lo adjunta a la factura en Zoho Books"""
    org_id = config['zoho']['organization_id']

    # Descargar PDF desde INFILE
    print(f"   Descargando PDF de INFILE...")
    try:
        response_pdf = requests.get(url_pdf, timeout=30)
        if response_pdf.status_code != 200:
            print(f"   [DEBUG] Error al descargar PDF: HTTP {response_pdf.status_code}")
            return False

        # Verificar que es un PDF
        content_type = response_pdf.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not response_pdf.content[:5] == b'%PDF-':
            print(f"   [DEBUG] La respuesta no es un PDF (Content-Type: {content_type})")
            return False
    except Exception as e:
        print(f"   [DEBUG] Error de conexion al descargar PDF: {e}")
        return False

    # Guardar en archivo temporal y subir a Zoho
    nombre_archivo = f"FEL_{serie}_{numero}.pdf"
    temp_path = os.path.join(tempfile.gettempdir(), nombre_archivo)

    try:
        with open(temp_path, 'wb') as f:
            f.write(response_pdf.content)

        # Subir a Zoho Books como adjunto
        url_attach = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}/attachment"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }
        params = {"organization_id": org_id}

        with open(temp_path, 'rb') as f:
            files = {'attachment': (nombre_archivo, f, 'application/pdf')}
            response_attach = requests.post(url_attach, headers=headers, params=params, files=files)

        if response_attach.status_code == 200:
            print(f"   PDF adjuntado: {nombre_archivo}")
            return True
        else:
            print(f"   [DEBUG] Error al adjuntar PDF: {response_attach.status_code}")
            try:
                print(f"   [DEBUG] Mensaje: {response_attach.json().get('message', '')}")
            except:
                print(f"   [DEBUG] Respuesta: {response_attach.text[:200]}")
            return False
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)

def obtener_facturas_certificadas(config, access_token):
    """Obtiene facturas certificadas (sent) que tienen fel_uuid y fel_estado=Certificada"""
    org_id = config['zoho']['organization_id']
    url = f"{config['zoho']['api_domain']}/books/v3/invoices"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {
        "organization_id": org_id,
        "status": "sent"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error al obtener facturas: {response.text}")
        return []

    facturas = response.json().get('invoices', [])
    certificadas = []

    for factura in facturas:
        invoice_id = factura.get('invoice_id')
        detalle = obtener_detalle_factura(config, access_token, invoice_id)
        if not detalle:
            continue

        custom_fields = detalle.get('custom_fields', [])
        fel_uuid = ''
        fel_estado = ''
        for cf in custom_fields:
            label = cf.get('label', '')
            if label == 'fel_uuid':
                fel_uuid = cf.get('value', '') or ''
            elif label == 'fel_estado':
                fel_estado = cf.get('value', '') or ''

        if fel_uuid and fel_estado == 'Certificada':
            # Guardar el detalle cacheado para no volver a consultar
            factura['_detalle'] = detalle
            factura['_fel_uuid'] = fel_uuid
            certificadas.append(factura)

    return certificadas

def mostrar_menu_anulacion(facturas):
    """Muestra el menu de facturas certificadas para anular"""
    print("\n" + "="*70)
    print("      ASISTENTE DE FACTURACION ADSTTER - ANULACION FEL")
    print("="*70)

    if not facturas:
        print("\nNo hay facturas certificadas para anular.")
        return []

    print(f"\nFacturas certificadas encontradas: {len(facturas)}\n")
    print("-"*70)
    print(f"{'#':<4} {'Numero':<25} {'Cliente':<25} {'UUID FEL':<16}")
    print("-"*70)

    for i, factura in enumerate(facturas, 1):
        numero = factura.get('invoice_number', 'N/A')
        cliente = factura.get('customer_name', 'N/A')[:23]
        fel_uuid = factura.get('_fel_uuid', '')
        uuid_corto = fel_uuid[:12] + '...' if len(fel_uuid) > 12 else fel_uuid
        print(f"{i:<4} {numero:<25} {cliente:<25} {uuid_corto:<16}")

    print("-"*70)
    print("\nOpciones:")
    print("  - Ingrese numeros separados por coma (ej: 1,3,5)")
    print("  - Ingrese 'T' para seleccionar todas")
    print("  - Ingrese '0' para volver")
    print("-"*70)

    seleccion = input("\nSeleccione las facturas a anular: ").strip()

    if seleccion == '0':
        return []

    if seleccion.upper() == 'T':
        return list(range(len(facturas)))

    try:
        indices = [int(x.strip()) - 1 for x in seleccion.split(',')]
        indices = [i for i in indices if 0 <= i < len(facturas)]
        return indices
    except:
        print("Seleccion invalida.")
        return []

def generar_xml_anulacion(config, factura_detalle, contacto):
    """Genera el XML de anulacion FEL para INFILE"""
    emisor = config['emisor']

    # Obtener datos FEL de la factura certificada
    custom_fields = factura_detalle.get('custom_fields', [])
    fel_uuid = ''
    fel_fecha_certificacion = ''
    for cf in custom_fields:
        label = cf.get('label', '')
        if label == 'fel_uuid':
            fel_uuid = cf.get('value', '') or ''
        elif label == 'fel_fecha_certificacion':
            fel_fecha_certificacion = cf.get('value', '') or ''

    # Reconstruir IDReceptor con la misma logica que generar_xml_factura
    nit_receptor = ''
    custom_fields_contacto = contacto.get('custom_fields', [])
    for cf in custom_fields_contacto:
        label = cf.get('label', '').upper().strip()
        if 'NIT' in label or 'ID DE EMPRESA' in label or label in ['TAX ID', 'TAX NUMBER', 'NUMERO FISCAL', 'ID FISCAL', 'RFC', 'RUC', 'RUT', 'ID EMPRESA']:
            nit_receptor = cf.get('value', '') or ''
            if nit_receptor and nit_receptor.upper() not in ['N/A', 'CF', '']:
                break

    if not nit_receptor or nit_receptor.upper() in ['N/A', 'CF', '']:
        nit_receptor = contacto.get('tax_number', '') or ''

    nit_receptor = ''.join(c for c in str(nit_receptor) if c.isalnum() or c == '-')
    if not nit_receptor or nit_receptor.upper() in ['CF', 'C/F', 'CONSUMIDORFINAL', 'CONSUMIDOR FINAL', 'N/A']:
        nit_receptor = 'CF'
    nit_receptor = nit_receptor.upper()

    # Para exportaciones, el ID del receptor es CF
    direccion_receptor = contacto.get('billing_address', {}) or {}
    pais_cliente = (direccion_receptor.get('country', '') or '').strip().lower()
    paises_locales = ['guatemala', 'gt', 'gua', '']
    es_exportacion = pais_cliente not in paises_locales
    id_receptor = "CF" if es_exportacion else nit_receptor

    # Fecha y hora actual para la anulacion
    fecha_anulacion = datetime.now().strftime('%Y-%m-%dT%H:%M:%S-06:00')

    # Namespace para anulacion (diferente al de certificacion)
    ns = "http://www.sat.gob.gt/dte/fel/0.1.0"

    xml_lines = []
    xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_lines.append(f'<dte:GTAnulacionDocumento xmlns:dte="{ns}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" Version="0.1">')
    xml_lines.append('  <dte:SAT>')
    xml_lines.append('    <dte:AnulacionDTE ID="DatosCertificados">')
    xml_lines.append(f'      <dte:DatosGenerales ID="DatosAnulacion" NumeroDocumentoAAnular="{fel_uuid}" NITEmisor="{emisor["nit"]}" IDReceptor="{id_receptor}" FechaEmisionDocumentoAnular="{fel_fecha_certificacion}" FechaHoraAnulacion="{fecha_anulacion}" MotivoAnulacion="Anulacion"/>')
    xml_lines.append('    </dte:AnulacionDTE>')
    xml_lines.append('  </dte:SAT>')
    xml_lines.append('</dte:GTAnulacionDocumento>')

    return '\n'.join(xml_lines)

def actualizar_factura_zoho_anulacion(config, access_token, invoice_id):
    """Actualiza la factura en Zoho despues de anulacion exitosa en SAT"""
    org_id = config['zoho']['organization_id']
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    params = {"organization_id": org_id}

    # 1. Marcar factura como void en Zoho (debe hacerse ANTES de actualizar campos)
    url_void = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}/status/void"
    response_void = requests.post(url_void, headers=headers, params=params)
    if response_void.status_code != 200:
        print(f"   [DEBUG] Error al marcar como void: {response_void.status_code}")
        try:
            resp_json = response_void.json()
            print(f"   [DEBUG] Mensaje: {resp_json.get('message', '')}")
            print(f"   [DEBUG] Respuesta completa: {resp_json}")
        except:
            print(f"   [DEBUG] Respuesta: {response_void.text[:300]}")
        return False

    print("   Factura marcada como void en Zoho")

    # 2. Actualizar custom field fel_estado a "Anulada"
    url_update = f"{config['zoho']['api_domain']}/books/v3/invoices/{invoice_id}"
    data = {
        "reason": "Anulacion FEL en SAT",
        "custom_fields": [
            {"label": "fel_estado", "value": "Anulada"}
        ]
    }
    response = requests.put(url_update, headers=headers, params=params, json=data)
    if response.status_code != 200:
        print(f"   [DEBUG] Error al actualizar fel_estado: {response.status_code}")
        try:
            print(f"   [DEBUG] Mensaje: {response.json().get('message', '')}")
        except:
            pass
        print("   AVISO: La factura ya fue marcada como void, pero no se pudo actualizar fel_estado")
        return True  # El void ya se hizo, es lo importante

    print("   fel_estado actualizado a: Anulada")
    return True

def flujo_anulacion(config, access_token):
    """Flujo completo de anulacion de facturas certificadas"""
    print("\nObteniendo facturas certificadas...")
    facturas = obtener_facturas_certificadas(config, access_token)
    indices_seleccionados = mostrar_menu_anulacion(facturas)

    if not indices_seleccionados:
        return

    # Confirmar anulacion
    print(f"\n*** ATENCION: Se anularan {len(indices_seleccionados)} factura(s) en SAT ***")
    confirmar = input("Escriba 'SI' para confirmar: ").strip()
    if confirmar != 'SI':
        print("Anulacion cancelada.")
        return

    print(f"\n{'='*70}")
    print(f"Anulando {len(indices_seleccionados)} factura(s)...")
    print(f"{'='*70}\n")

    resultados = {
        'exitosas': [],
        'fallidas': []
    }

    for idx in indices_seleccionados:
        factura = facturas[idx]
        invoice_id = factura.get('invoice_id')
        invoice_number = factura.get('invoice_number', 'N/A')
        fel_uuid = factura.get('_fel_uuid', '')

        print(f"\n>> Anulando factura: {invoice_number}")
        print(f"   UUID: {fel_uuid}")
        print("-"*50)

        # Obtener detalle (ya cacheado)
        detalle = factura.get('_detalle')
        if not detalle:
            detalle = obtener_detalle_factura(config, access_token, invoice_id)
        if not detalle:
            print("   ERROR: No se pudo obtener el detalle de la factura")
            resultados['fallidas'].append({'numero': invoice_number, 'error': 'No se pudo obtener detalle'})
            continue

        # Obtener datos del contacto
        contact_id = detalle.get('customer_id')
        print("   Obteniendo datos del cliente...")
        contacto = obtener_contacto(config, access_token, contact_id) or {}

        # Generar XML de anulacion
        print("   Generando XML de anulacion...")
        xml_content = generar_xml_anulacion(config, detalle, contacto)

        # Enviar a INFILE (mismo endpoint de certificacion)
        identificador = f"ANULA_{invoice_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print("   Enviando a INFILE para anulacion...")
        resultado = certificar_factura_infile(config, xml_content, identificador)

        if resultado.get('resultado') == True:
            print(f"   ANULADA EXITOSAMENTE EN SAT!")

            # Actualizar Zoho
            print("   Actualizando factura en Zoho...")
            exito = actualizar_factura_zoho_anulacion(config, access_token, invoice_id)
            if not exito:
                print("   AVISO: No se pudo actualizar Zoho, pero la factura SI fue anulada en SAT")

            resultados['exitosas'].append({
                'numero': invoice_number,
                'uuid': fel_uuid
            })
        else:
            error = resultado.get('descripcion', 'Error desconocido')
            errores_detalle = resultado.get('descripcion_errores', [])

            print(f"   ERROR EN ANULACION:")
            print(f"   {error}")
            if errores_detalle:
                for err in errores_detalle[:5]:
                    if isinstance(err, dict):
                        msg = err.get('mensaje_error', '')
                        cat = err.get('categoria', '')
                        print(f"   - [{cat}] {msg}")
                    else:
                        print(f"   - {err}")

            resultados['fallidas'].append({
                'numero': invoice_number,
                'error': error
            })

    # Resumen
    print("\n" + "="*70)
    print("                    RESUMEN ANULACION")
    print("="*70)
    print(f"\nFacturas procesadas: {len(indices_seleccionados)}")
    print(f"Anuladas: {len(resultados['exitosas'])}")
    print(f"Fallidas: {len(resultados['fallidas'])}")

    if resultados['exitosas']:
        print("\n--- Facturas Anuladas ---")
        for f in resultados['exitosas']:
            print(f"  {f['numero']} -> UUID: {f['uuid']}")

    if resultados['fallidas']:
        print("\n--- Facturas con Error ---")
        for f in resultados['fallidas']:
            print(f"  {f['numero']} -> {f['error'][:50]}")

    print("\n" + "="*70)

def flujo_certificacion(config, access_token):
    """Flujo completo de certificacion de facturas borrador"""
    print("Obteniendo facturas en borrador...")

    facturas = obtener_facturas_borrador(config, access_token)
    indices_seleccionados = mostrar_menu_facturas(facturas)

    if not indices_seleccionados:
        return

    print(f"\n{'='*70}")
    print(f"Procesando {len(indices_seleccionados)} factura(s)...")
    print(f"{'='*70}\n")

    resultados = {
        'exitosas': [],
        'fallidas': []
    }

    for idx in indices_seleccionados:
        factura = facturas[idx]
        invoice_id = factura.get('invoice_id')
        invoice_number = factura.get('invoice_number', 'N/A')

        print(f"\n>> Procesando factura: {invoice_number}")
        print("-"*50)

        # Obtener detalle completo
        print("   Obteniendo detalle de factura...")
        detalle = obtener_detalle_factura(config, access_token, invoice_id)
        if not detalle:
            print("   ERROR: No se pudo obtener el detalle de la factura")
            resultados['fallidas'].append({'numero': invoice_number, 'error': 'No se pudo obtener detalle'})
            continue

        # Obtener datos del contacto
        contact_id = detalle.get('customer_id')
        print("   Obteniendo datos del cliente...")
        contacto = obtener_contacto(config, access_token, contact_id) or {}

        # Detectar si es exportación (para no aplicar limite CF)
        # Si el país está vacío, asumir que es LOCAL (Guatemala)
        direccion_cliente = contacto.get('billing_address', {}) or {}
        pais_cliente = (direccion_cliente.get('country', '') or '').strip().lower()
        # Lista de valores que indican Guatemala o local
        paises_locales = ['guatemala', 'gt', 'gua', '']
        es_exportacion = pais_cliente not in paises_locales

        if es_exportacion:
            print(f"   [INFO] Factura de EXPORTACION detectada (pais: {pais_cliente})")

        # Validar NIT para montos altos (solo aplica a ventas locales)
        # SIEMPRE buscar primero en campos personalizados (tienen prioridad)
        nit_cliente = ''
        custom_fields_contacto = contacto.get('custom_fields', [])
        for cf in custom_fields_contacto:
            label = cf.get('label', '').upper().strip()
            # Buscar cualquier campo que contenga "NIT" o sea identificador fiscal
            # Incluye "ID DE EMPRESA" que es donde Zoho guarda el NIT
            if 'NIT' in label or 'ID DE EMPRESA' in label or label in ['TAX ID', 'TAX NUMBER', 'NUMERO FISCAL', 'ID FISCAL', 'RFC', 'RUC', 'RUT', 'ID EMPRESA']:
                nit_cliente = cf.get('value', '') or ''
                if nit_cliente and nit_cliente.upper() not in ['N/A', 'CF', '']:
                    break

        # Si no hay NIT en campos personalizados, usar tax_number como fallback
        if not nit_cliente or nit_cliente.upper() in ['N/A', 'CF', '']:
            nit_cliente = contacto.get('tax_number', '') or ''

        total_factura = float(detalle.get('total', 0))
        moneda_factura = detalle.get('currency_code', 'GTQ')

        # Limite para CF en Guatemala es Q2,500 (no aplica a exportaciones)
        LIMITE_CF_GTQ = 2500.00

        es_consumidor_final = not nit_cliente or nit_cliente.upper() in ['CF', 'C/F', 'N/A', '']

        # La validación de límite CF solo aplica a ventas LOCALES, no a exportaciones
        if es_consumidor_final and moneda_factura == 'GTQ' and total_factura > LIMITE_CF_GTQ and not es_exportacion:
            print(f"   ERROR: Factura a Consumidor Final excede limite de Q{LIMITE_CF_GTQ:,.2f}")
            print(f"   Total: Q{total_factura:,.2f} - Se requiere NIT del cliente")
            print(f"   >> Configura el NIT del cliente '{detalle.get('customer_name', 'N/A')}' en Zoho Books")
            resultados['fallidas'].append({
                'numero': invoice_number,
                'error': f'CF excede limite Q{LIMITE_CF_GTQ}. Configura NIT en Zoho.'
            })
            continue

        # Generar XML
        print("   Generando XML FEL...")
        xml_content = generar_xml_factura(config, detalle, contacto)

        # Generar identificador unico
        identificador = f"ADSTTER_{invoice_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Certificar con INFILE
        print("   Enviando a INFILE para certificacion...")
        resultado_cert = certificar_factura_infile(config, xml_content, identificador)

        if resultado_cert.get('resultado') == True:
            uuid_fel = resultado_cert.get('uuid', '')
            serie = resultado_cert.get('serie', '')
            numero = resultado_cert.get('numero', '')
            # Construir URL del PDF de INFILE usando el UUID
            url_pdf = f"https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid={uuid_fel}"
            url_xml = f"https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid={uuid_fel}"

            print(f"   CERTIFICADA EXITOSAMENTE!")
            print(f"   UUID: {uuid_fel}")
            print(f"   Serie: {serie} | Numero: {numero}")
            print(f"   Ver PDF: {url_pdf}")

            # Guardar URLs en resultado para usar en actualizacion
            resultado_cert['url_pdf_infile'] = url_pdf
            resultado_cert['url_xml_infile'] = url_xml

            # DEBUG: Mostrar todos los campos de la respuesta de INFILE
            print(f"   [DEBUG] Campos INFILE: {list(resultado_cert.keys())}")

            # Actualizar factura en Zoho (esto tambien marca como enviada)
            print("   Actualizando factura en Zoho...")
            exito_actualizacion = actualizar_factura_zoho(config, access_token, invoice_id, resultado_cert)

            if not exito_actualizacion:
                print("   AVISO: No se pudo actualizar numero/fecha en Zoho, pero la factura SI fue certificada en SAT")

            # Descargar PDF de INFILE y adjuntar a la factura en Zoho
            descargar_y_adjuntar_pdf_fel(config, access_token, invoice_id, url_pdf, serie, numero)

            # Enviar por email con datos de certificacion
            emails = contacto.get('email', '')
            if emails:
                print(f"   Enviando por email a: {emails}")
                enviar_factura_email(config, access_token, invoice_id, emails, resultado_cert, contacto)
            else:
                print("   AVISO: El cliente no tiene email configurado")

            resultados['exitosas'].append({
                'numero': invoice_number,
                'uuid': uuid_fel,
                'serie': serie,
                'numero_fel': numero
            })
        else:
            error = resultado_cert.get('descripcion', 'Error desconocido')
            errores_detalle = resultado_cert.get('descripcion_errores', [])

            print(f"   ERROR EN CERTIFICACION:")
            print(f"   {error}")
            if errores_detalle:
                for err in errores_detalle[:5]:  # Mostrar max 5 errores
                    if isinstance(err, dict):
                        msg = err.get('mensaje_error', '')
                        cat = err.get('categoria', '')
                        print(f"   - [{cat}] {msg}")
                    else:
                        print(f"   - {err}")

            # Mostrar info del cliente para depuracion
            print(f"   [DEBUG] Cliente: {contacto.get('contact_name', 'N/A')}")
            print(f"   [DEBUG] NIT: {contacto.get('tax_number', 'N/A')}")

            resultados['fallidas'].append({
                'numero': invoice_number,
                'error': error
            })

    # Resumen final
    print("\n" + "="*70)
    print("                         RESUMEN")
    print("="*70)
    print(f"\nFacturas procesadas: {len(indices_seleccionados)}")
    print(f"Exitosas: {len(resultados['exitosas'])}")
    print(f"Fallidas: {len(resultados['fallidas'])}")

    if resultados['exitosas']:
        print("\n--- Facturas Certificadas ---")
        for f in resultados['exitosas']:
            print(f"  {f['numero']} -> UUID: {f['uuid']}")

    if resultados['fallidas']:
        print("\n--- Facturas con Error ---")
        for f in resultados['fallidas']:
            print(f"  {f['numero']} -> {f['error'][:50]}")

    print("\n" + "="*70)

def main():
    """Funcion principal del asistente"""
    print("\nCargando configuracion...")

    try:
        config = cargar_config()
    except Exception as e:
        print(f"Error al cargar configuracion: {e}")
        input("\nPresione Enter para salir...")
        return

    ambiente = config['infile'].get('ambiente', 'PRUEBAS')
    print(f"\n*** AMBIENTE: {ambiente} ***")
    if ambiente == 'PRUEBAS':
        print("*** Las facturas NO tendran validez fiscal ***\n")

    print("Conectando con Zoho Books...")
    access_token = obtener_access_token(config)

    if not access_token:
        print("No se pudo conectar con Zoho Books.")
        input("\nPresione Enter para salir...")
        return

    print("Conexion exitosa!\n")

    while True:
        print("="*70)
        print("      ASISTENTE DE FACTURACION ADSTTER")
        print("="*70)
        print("\n  1) Certificar facturas (borrador -> FEL)")
        print("  2) Anular facturas (certificadas -> anulacion SAT)")
        print("  0) Salir")
        print("-"*70)

        opcion = input("\nSeleccione una opcion: ").strip()

        if opcion == '1':
            flujo_certificacion(config, access_token)
        elif opcion == '2':
            flujo_anulacion(config, access_token)
        elif opcion == '0':
            print("\nSaliendo...")
            break
        else:
            print("\nOpcion invalida. Intente de nuevo.")

    input("\nPresione Enter para salir...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n" + "="*70)
        print("ERROR INESPERADO:")
        print(str(e))
        print("="*70)
        input("\nPresione Enter para salir...")
