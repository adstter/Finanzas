// ============================================
// PRESUPUESTO 2026 - DASHBOARD EJECUTIVO
// ============================================

// Variables globales
let datosPresupuesto = null;
let charts = {};
let ventasProductos = Array(12).fill(0); // Ventas mensuales de productos
const MARGEN_PRODUCTOS = 0.30; // 30% margen bruto

// Meses para referencias
const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const MESES_FULL = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

// Colores para graficos
const COLORES = {
    primario: '#1e3a8a',
    secundario: '#3b82f6',
    exito: '#10b981',
    peligro: '#ef4444',
    advertencia: '#f59e0b',
    info: '#06b6d4',
    gris: '#6b7280',
    palette: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1']
};

// ============================================
// INICIALIZACION
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    inicializarUpload();
    inicializarNavegacion();
    inicializarVentas();
    cargarDatosGuardados();
    cargarVentasGuardadas();
});

// ============================================
// CARGA DE ARCHIVOS
// ============================================
function inicializarUpload() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    // Click para seleccionar archivo (busca el input actual)
    uploadZone.addEventListener('click', (e) => {
        // Evitar que el click en el input dispare doble
        if (e.target.tagName === 'INPUT') return;

        const currentInput = document.getElementById('fileInput');
        if (currentInput) {
            currentInput.click();
        }
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) procesarArchivo(file);
    });

    // Input file change (inicial)
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) procesarArchivo(file);
        });
    }
}

function procesarArchivo(file) {
    const uploadZone = document.getElementById('uploadZone');

    if (!file.name.match(/\.(xlsx|xls)$/i)) {
        alert('Por favor selecciona un archivo Excel (.xlsx o .xls)');
        return;
    }

    // Mostrar estado de carga
    uploadZone.innerHTML = `
        <div class="upload-icon">&#9203;</div>
        <h3>Cargando archivo...</h3>
        <p>Procesando ${file.name}</p>
        <input type="file" id="fileInput" accept=".xlsx,.xls" style="display: none;">
    `;

    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            console.log('Leyendo archivo Excel...');
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: 'array' });

            console.log('Hojas encontradas:', workbook.SheetNames);

            // Buscar hoja "Presupuesto 2026"
            const sheetName = workbook.SheetNames.find(name => name.includes('Presupuesto 2026')) || workbook.SheetNames[0];
            console.log('Usando hoja:', sheetName);

            const worksheet = workbook.Sheets[sheetName];

            console.log('Convirtiendo a JSON...');

            // Usar setTimeout para no bloquear el navegador
            setTimeout(() => {
                try {
                    // Convertir a JSON - SOLO las filas necesarias (A1:P160)
                    const rango = { s: { r: 0, c: 0 }, e: { r: 159, c: 15 } }; // Filas 1-160, Columnas A-P
                    const jsonData = XLSX.utils.sheet_to_json(worksheet, {
                        header: 1,
                        defval: 0,
                        range: rango
                    });
                    console.log('Filas extraidas:', jsonData.length);

                    // Extraer datos
                    datosPresupuesto = extraerDatos(jsonData);
                    console.log('Datos extraidos OK');

                    // Guardar en localStorage
                    localStorage.setItem('presupuesto2026', JSON.stringify(datosPresupuesto));
                    localStorage.setItem('presupuesto2026_fecha', new Date().toISOString());

                    // Actualizar UI
                    uploadZone.classList.add('loaded');
                    uploadZone.innerHTML = `
                        <div class="upload-icon">&#9989;</div>
                        <h3>Archivo cargado correctamente</h3>
                        <p>${file.name} - Haz clic para actualizar</p>
                        <input type="file" id="fileInput" accept=".xlsx,.xls" style="display: none;">
                    `;

                    // Re-vincular el evento del input
                    document.getElementById('fileInput').addEventListener('change', (e) => {
                        const newFile = e.target.files[0];
                        if (newFile) procesarArchivo(newFile);
                    });

                    actualizarLastUpdate();
                    renderizarDashboard();

                } catch (innerError) {
                    console.error('Error procesando datos:', innerError);
                    alert('Error: ' + innerError.message);
                }
            }, 100);

        } catch (error) {
            console.error('Error procesando archivo:', error);
            alert('Error al procesar el archivo: ' + error.message);

            // Restaurar zona de carga
            uploadZone.classList.remove('loaded');
            uploadZone.innerHTML = `
                <div class="upload-icon">&#128200;</div>
                <h3>Cargar Presupuesto Excel</h3>
                <p>Arrastra el archivo "Presupuesto 2026.xlsx" aqui o haz clic para seleccionar</p>
                <input type="file" id="fileInput" accept=".xlsx,.xls" style="display: none;">
            `;
            document.getElementById('fileInput').addEventListener('change', (e) => {
                const newFile = e.target.files[0];
                if (newFile) procesarArchivo(newFile);
            });
        }
    };

    reader.onerror = function(error) {
        console.error('Error leyendo archivo:', error);
        alert('Error al leer el archivo.');
    };

    reader.readAsArrayBuffer(file);
}

// ============================================
// EXTRACCION DE DATOS
// ============================================
function extraerDatos(data) {
    console.log('Iniciando extraccion de datos...');
    console.log('Total filas:', data.length);

    const resultado = {
        ingresos: {
            clientes: [],
            totalMensual: [],
            totalAnual: 0
        },
        costos: {
            detalle: [],
            totalMensual: [],
            totalAnual: 0
        },
        margenBruto: {
            mensual: [],
            anual: 0,
            porcentaje: 0
        },
        opex: {
            consultores: [],
            software: [],
            otros: [],
            totalMensual: [],
            totalAnual: 0
        },
        resultado: {
            mensual: [],
            anual: 0,
            margenOperativo: 0
        },
        gastos: []
    };

    // Extraer clientes (filas 2-50, columnas: 1=nombre, 3-14=meses, 15=total)
    for (let i = 2; i <= 50; i++) {
        if (data[i] && data[i][1] && typeof data[i][1] === 'string' && data[i][1].trim() !== '') {
            const nombre = data[i][1].trim();
            // Ignorar filas que son titulos o vacias
            if (nombre.toLowerCase().includes('ingresos') ||
                nombre.toLowerCase().includes('ventas') ||
                nombre.toLowerCase().includes('total') ||
                nombre.toLowerCase().includes('reduccion')) continue;

            const mensual = [];
            let total = 0;
            for (let m = 3; m <= 14; m++) {
                const valor = parseFloat(data[i][m]) || 0;
                mensual.push(valor);
                total += valor;
            }

            if (total > 0) {
                resultado.ingresos.clientes.push({
                    nombre: nombre,
                    mensual: mensual,
                    total: parseFloat(data[i][15]) || total
                });
            }
        }
    }

    // Ordenar clientes por total descendente
    resultado.ingresos.clientes.sort((a, b) => b.total - a.total);
    console.log('Clientes encontrados:', resultado.ingresos.clientes.length);

    // Total Ingresos (fila 51)
    resultado.ingresos.totalMensual = extraerMensual(data, 51);
    resultado.ingresos.totalAnual = parseFloat(data[51]?.[15]) || sumar(resultado.ingresos.totalMensual);
    console.log('Total Ingresos:', resultado.ingresos.totalAnual);

    // Costos directos
    // Comisiones Atrevete (fila 61)
    agregarGasto(resultado.costos.detalle, data, 61, 'Comisiones Recurrentes (Atrevete)');
    // Comisiones Gerencia (fila 62)
    agregarGasto(resultado.costos.detalle, data, 62, 'Comisiones Gerencia Comercial');
    // Servidores (fila 63)
    agregarGasto(resultado.costos.detalle, data, 63, 'Costes de Servidores');

    // Total Costos (fila 67 - es la fila sin nombre con el total)
    resultado.costos.totalMensual = extraerMensual(data, 67);
    resultado.costos.totalAnual = parseFloat(data[67]?.[15]) || sumar(resultado.costos.totalMensual);
    console.log('Total Costos:', resultado.costos.totalAnual);

    // Margen Bruto (fila 69)
    resultado.margenBruto.mensual = extraerMensual(data, 69);
    resultado.margenBruto.anual = parseFloat(data[69]?.[15]) || sumar(resultado.margenBruto.mensual);
    resultado.margenBruto.porcentaje = resultado.ingresos.totalAnual > 0
        ? (resultado.margenBruto.anual / resultado.ingresos.totalAnual * 100)
        : 0;
    console.log('Margen Bruto:', resultado.margenBruto.anual);

    // OPEX - Consultores (filas 72-78)
    for (let i = 72; i <= 78; i++) {
        agregarGastoOPEX(resultado.opex.consultores, data, i, 'Consultores');
    }

    // OPEX - Software (filas 88-104)
    for (let i = 88; i <= 104; i++) {
        agregarGastoOPEX(resultado.opex.software, data, i, 'Software');
    }

    // OPEX - Otros gastos (filas 110-115)
    for (let i = 110; i <= 115; i++) {
        agregarGastoOPEX(resultado.opex.otros, data, i, 'Otros');
    }

    // Total OPEX / Gastos de Explotacion (fila 122 en Excel = indice 121)
    resultado.opex.totalMensual = extraerMensual(data, 121);
    resultado.opex.totalAnual = parseFloat(data[121]?.[15]) || sumar(resultado.opex.totalMensual);
    console.log('Total OPEX:', resultado.opex.totalAnual);

    // Resultado (fila 151 en Excel = indice 150)
    resultado.resultado.mensual = extraerMensual(data, 150);
    resultado.resultado.anual = parseFloat(data[150]?.[15]) || sumar(resultado.resultado.mensual);
    resultado.resultado.margenOperativo = resultado.ingresos.totalAnual > 0
        ? (resultado.resultado.anual / resultado.ingresos.totalAnual * 100)
        : 0;
    console.log('Resultado:', resultado.resultado.anual);

    // Consolidar todos los gastos para ranking
    resultado.gastos = [
        ...resultado.costos.detalle,
        ...resultado.opex.consultores,
        ...resultado.opex.software,
        ...resultado.opex.otros
    ].filter(g => g.total > 0).sort((a, b) => b.total - a.total);

    console.log('Extraccion completada');
    return resultado;
}

function extraerMensual(data, fila) {
    const mensual = [];
    if (data[fila]) {
        for (let m = 3; m <= 14; m++) {
            mensual.push(parseFloat(data[fila][m]) || 0);
        }
    }
    return mensual;
}

function agregarGasto(lista, data, fila, nombreDefault) {
    if (data[fila]) {
        const nombre = data[fila][1] || nombreDefault;
        if (nombre && typeof nombre === 'string' && nombre.trim() !== '') {
            const mensual = extraerMensual(data, fila);
            const total = data[fila][15] || sumar(mensual);
            if (total > 0) {
                lista.push({
                    nombre: nombre.trim(),
                    mensual: mensual,
                    total: total
                });
            }
        }
    }
}

function agregarGastoOPEX(lista, data, fila, categoria) {
    if (data[fila] && data[fila][1]) {
        const nombre = data[fila][1];
        if (typeof nombre === 'string' && nombre.trim() !== '' && !nombre.includes('NaN')) {
            const mensual = extraerMensual(data, fila);
            const total = data[fila][15] || sumar(mensual);
            if (total > 0) {
                lista.push({
                    nombre: nombre.trim(),
                    categoria: categoria,
                    mensual: mensual,
                    total: total
                });
            }
        }
    }
}

function buscarFila(data, texto, filaInicio) {
    for (let i = filaInicio; i < data.length; i++) {
        if (data[i] && data[i][1] && typeof data[i][1] === 'string' && data[i][1].includes(texto)) {
            return i;
        }
    }
    return null;
}

function sumar(arr) {
    return arr.reduce((a, b) => a + b, 0);
}

// ============================================
// RENDERIZADO DEL DASHBOARD
// ============================================
function renderizarDashboard() {
    if (!datosPresupuesto) return;

    renderizarKPIs();
    renderizarPL();
    renderizarIngresos();
    renderizarCostos();
    renderizarOPEX();
    renderizarRankings();
    renderizarPLConsolidado();
}

// KPIs
function renderizarKPIs() {
    const d = datosPresupuesto;

    document.getElementById('kpi-ingresos').textContent = formatoMoneda(d.ingresos.totalAnual);
    document.getElementById('kpi-margen-bruto').textContent = d.margenBruto.porcentaje.toFixed(1) + '%';
    document.getElementById('kpi-margen-bruto-monto').textContent = formatoMoneda(d.margenBruto.anual);
    document.getElementById('kpi-costos').textContent = formatoMoneda(d.costos.totalAnual);
    document.getElementById('kpi-opex').textContent = formatoMoneda(d.opex.totalAnual);
    document.getElementById('kpi-resultado').textContent = formatoMoneda(d.resultado.anual);
    document.getElementById('kpi-margen-operativo').textContent = 'Margen: ' + d.resultado.margenOperativo.toFixed(1) + '%';

    // Color del resultado
    const resultadoCard = document.getElementById('kpi-resultado-card');
    if (d.resultado.anual >= 0) {
        resultadoCard.classList.remove('danger');
        resultadoCard.classList.add('success');
    } else {
        resultadoCard.classList.remove('success');
        resultadoCard.classList.add('danger');
    }
}

// Estado de Resultados
function renderizarPL() {
    const d = datosPresupuesto;

    // === VISTA RESUMIDA ===
    const tbodyResumido = document.getElementById('pl-body-resumido');
    const filasResumidas = [
        { concepto: '(+) Ingresos Totales', datos: d.ingresos.totalMensual, total: d.ingresos.totalAnual, clase: '' },
        { concepto: '(-) Costos Directos', datos: d.costos.totalMensual, total: d.costos.totalAnual, clase: '' },
        { concepto: '(=) Margen Bruto', datos: d.margenBruto.mensual, total: d.margenBruto.anual, clase: 'subtotal-row' },
        { concepto: '(-) Gastos Operativos (OPEX)', datos: d.opex.totalMensual, total: d.opex.totalAnual, clase: '' },
        { concepto: '(=) Resultado Neto', datos: d.resultado.mensual, total: d.resultado.anual, clase: 'total-row' }
    ];

    tbodyResumido.innerHTML = filasResumidas.map(f => `
        <tr class="${f.clase}">
            <td><strong>${f.concepto}</strong></td>
            ${f.datos.map(v => `<td class="number ${v < 0 ? 'negative' : ''}">${formatoMonedaCorto(v)}</td>`).join('')}
            <td class="number"><strong>${formatoMonedaCorto(f.total)}</strong></td>
        </tr>
    `).join('');

    // === VISTA DETALLADA ===
    const tbodyDetallado = document.getElementById('pl-body-detallado');
    let htmlDetallado = '';

    // INGRESOS
    htmlDetallado += crearFilaCategoria('INGRESOS', d.ingresos.totalMensual, d.ingresos.totalAnual, 'positive');
    d.ingresos.clientes.slice(0, 20).forEach(cliente => {
        htmlDetallado += crearFilaDetalle(cliente.nombre, cliente.mensual, cliente.total);
    });
    if (d.ingresos.clientes.length > 20) {
        const otrosClientes = d.ingresos.clientes.slice(20);
        const otrosMensual = Array(12).fill(0);
        let otrosTotal = 0;
        otrosClientes.forEach(c => {
            c.mensual.forEach((v, i) => otrosMensual[i] += v);
            otrosTotal += c.total;
        });
        htmlDetallado += crearFilaDetalle(`Otros clientes (${otrosClientes.length})`, otrosMensual, otrosTotal);
    }
    htmlDetallado += crearFilaSubtotal('Total Ingresos', d.ingresos.totalMensual, d.ingresos.totalAnual);

    // COSTOS DIRECTOS
    htmlDetallado += crearFilaCategoria('COSTOS DIRECTOS', d.costos.totalMensual, d.costos.totalAnual, 'negative');
    d.costos.detalle.forEach(costo => {
        htmlDetallado += crearFilaDetalle(costo.nombre, costo.mensual, costo.total);
    });
    htmlDetallado += crearFilaSubtotal('Total Costos', d.costos.totalMensual, d.costos.totalAnual);

    // MARGEN BRUTO
    htmlDetallado += crearFilaResultado('MARGEN BRUTO', d.margenBruto.mensual, d.margenBruto.anual, d.margenBruto.porcentaje);

    // GASTOS OPERATIVOS
    htmlDetallado += crearFilaCategoria('GASTOS OPERATIVOS (OPEX)', d.opex.totalMensual, d.opex.totalAnual, 'negative');

    // Consultores
    if (d.opex.consultores.length > 0) {
        const totalConsultoresMensual = Array(12).fill(0);
        let totalConsultores = 0;
        d.opex.consultores.forEach(g => {
            g.mensual.forEach((v, i) => totalConsultoresMensual[i] += v);
            totalConsultores += g.total;
        });
        htmlDetallado += crearFilaSubcategoria('Consultores', totalConsultoresMensual, totalConsultores);
        d.opex.consultores.forEach(gasto => {
            htmlDetallado += crearFilaDetalle(gasto.nombre, gasto.mensual, gasto.total);
        });
    }

    // Software
    if (d.opex.software.length > 0) {
        const totalSoftwareMensual = Array(12).fill(0);
        let totalSoftware = 0;
        d.opex.software.forEach(g => {
            g.mensual.forEach((v, i) => totalSoftwareMensual[i] += v);
            totalSoftware += g.total;
        });
        htmlDetallado += crearFilaSubcategoria('Software y Tecnologia', totalSoftwareMensual, totalSoftware);
        d.opex.software.forEach(gasto => {
            htmlDetallado += crearFilaDetalle(gasto.nombre, gasto.mensual, gasto.total);
        });
    }

    // Otros
    if (d.opex.otros.length > 0) {
        const totalOtrosMensual = Array(12).fill(0);
        let totalOtros = 0;
        d.opex.otros.forEach(g => {
            g.mensual.forEach((v, i) => totalOtrosMensual[i] += v);
            totalOtros += g.total;
        });
        htmlDetallado += crearFilaSubcategoria('Otros Gastos', totalOtrosMensual, totalOtros);
        d.opex.otros.forEach(gasto => {
            htmlDetallado += crearFilaDetalle(gasto.nombre, gasto.mensual, gasto.total);
        });
    }

    htmlDetallado += crearFilaSubtotal('Total OPEX', d.opex.totalMensual, d.opex.totalAnual);

    // RESULTADO FINAL
    htmlDetallado += crearFilaResultadoFinal('RESULTADO NETO', d.resultado.mensual, d.resultado.anual, d.resultado.margenOperativo);

    tbodyDetallado.innerHTML = htmlDetallado;

    // Grafico P&L
    renderizarGraficoPL(d);
}

// Funciones auxiliares para crear filas detalladas
function crearFilaCategoria(concepto, mensual, total, tipo) {
    const color = tipo === 'positive' ? '#dcfce7' : tipo === 'negative' ? '#fee2e2' : '#f3f4f6';
    return `
        <tr style="background: ${color}; font-weight: 700;">
            <td style="padding: 12px 10px;">${concepto}</td>
            ${mensual.map(v => `<td class="number">${formatoDecimal(v)}</td>`).join('')}
            <td class="number" style="font-weight: 700;">${formatoDecimal(total)}</td>
        </tr>
    `;
}

function crearFilaSubcategoria(concepto, mensual, total) {
    return `
        <tr style="background: #f8fafc; font-weight: 600;">
            <td style="padding-left: 20px;">${concepto}</td>
            ${mensual.map(v => `<td class="number">${formatoDecimal(v)}</td>`).join('')}
            <td class="number">${formatoDecimal(total)}</td>
        </tr>
    `;
}

function crearFilaDetalle(concepto, mensual, total) {
    return `
        <tr>
            <td style="padding-left: 35px; font-size: 0.9rem;">${concepto}</td>
            ${mensual.map(v => `<td class="number" style="font-size: 0.85rem;">${formatoDecimal(v)}</td>`).join('')}
            <td class="number" style="font-size: 0.85rem;">${formatoDecimal(total)}</td>
        </tr>
    `;
}

function crearFilaSubtotal(concepto, mensual, total) {
    return `
        <tr style="background: #e5e7eb; font-weight: 600;">
            <td style="padding-left: 10px;">${concepto}</td>
            ${mensual.map(v => `<td class="number">${formatoDecimal(v)}</td>`).join('')}
            <td class="number">${formatoDecimal(total)}</td>
        </tr>
    `;
}

function crearFilaResultado(concepto, mensual, total, porcentaje) {
    return `
        <tr style="background: #dbeafe; font-weight: 700;">
            <td style="padding: 12px 10px;">${concepto} (${porcentaje.toFixed(2)}%)</td>
            ${mensual.map(v => `<td class="number">${formatoDecimal(v)}</td>`).join('')}
            <td class="number">${formatoDecimal(total)}</td>
        </tr>
    `;
}

function crearFilaResultadoFinal(concepto, mensual, total, porcentaje) {
    const color = total >= 0 ? '#dcfce7' : '#fee2e2';
    return `
        <tr style="background: ${color}; font-weight: 700; font-size: 1.05rem;">
            <td style="padding: 15px 10px;">${concepto} (${porcentaje.toFixed(2)}%)</td>
            ${mensual.map(v => `<td class="number ${v < 0 ? 'negative' : ''}">${formatoDecimal(v)}</td>`).join('')}
            <td class="number ${total < 0 ? 'negative' : ''}">${formatoDecimal(total)}</td>
        </tr>
    `;
}

// Toggle entre vista resumida y detallada
function togglePL(vista) {
    document.getElementById('pl-resumido').style.display = vista === 'resumido' ? 'block' : 'none';
    document.getElementById('pl-detallado').style.display = vista === 'detallado' ? 'block' : 'none';

    document.getElementById('btn-pl-resumido').classList.toggle('active', vista === 'resumido');
    document.getElementById('btn-pl-detallado').classList.toggle('active', vista === 'detallado');
}

function renderizarGraficoPL(d) {
    // Grafico Doughnut - Distribucion Anual
    const ctxPie = document.getElementById('chart-pl-pie').getContext('2d');
    if (charts.plPie) charts.plPie.destroy();

    const totalEgresos = d.costos.totalAnual + d.opex.totalAnual;
    charts.plPie = new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: ['Ingresos', 'Costos Directos', 'OPEX'],
            datasets: [{
                data: [d.ingresos.totalAnual, d.costos.totalAnual, d.opex.totalAnual],
                backgroundColor: [COLORES.exito, COLORES.peligro, COLORES.advertencia]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    // Grafico Linea - Resultado Mensual
    const ctxLine = document.getElementById('chart-pl-line').getContext('2d');
    if (charts.plLine) charts.plLine.destroy();

    charts.plLine = new Chart(ctxLine, {
        type: 'line',
        data: {
            labels: MESES,
            datasets: [{
                label: 'Resultado Mensual',
                data: d.resultado.mensual,
                borderColor: COLORES.advertencia,
                backgroundColor: COLORES.advertencia + '20',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    ticks: {
                        callback: value => value.toLocaleString('es-GT')
                    }
                }
            }
        }
    });
}

// Ingresos
function renderizarIngresos() {
    const d = datosPresupuesto;

    document.getElementById('badge-clientes').textContent = d.ingresos.clientes.length + ' clientes';

    // Tabla de clientes
    const tbodyClientes = document.getElementById('clientes-body');
    let htmlClientes = '';

    d.ingresos.clientes.forEach((cliente, index) => {
        const porcentaje = (cliente.total / d.ingresos.totalAnual * 100).toFixed(2);
        htmlClientes += `
            <tr>
                <td>${index + 1}</td>
                <td>${cliente.nombre}</td>
                ${cliente.mensual.map(v => `<td class="number">${formatoDecimal(v)}</td>`).join('')}
                <td class="number"><strong>${formatoDecimal(cliente.total)}</strong></td>
                <td class="number">${porcentaje}%</td>
            </tr>
        `;
    });

    // Fila de totales
    htmlClientes += `
        <tr class="total-row">
            <td colspan="2"><strong>TOTAL</strong></td>
            ${d.ingresos.totalMensual.map(v => `<td class="number"><strong>${formatoDecimal(v)}</strong></td>`).join('')}
            <td class="number"><strong>${formatoDecimal(d.ingresos.totalAnual)}</strong></td>
            <td class="number"><strong>100%</strong></td>
        </tr>
    `;

    tbodyClientes.innerHTML = htmlClientes;

    // Top 10 para pie chart
    const top10 = d.ingresos.clientes.slice(0, 10);
    const otros = d.ingresos.clientes.slice(10);
    const otrosTotal = otros.reduce((sum, c) => sum + c.total, 0);

    // Pie Chart
    const ctxPie = document.getElementById('chart-ingresos-pie').getContext('2d');
    if (charts.ingresosPie) charts.ingresosPie.destroy();

    const pieData = [...top10.map(c => c.total)];
    const pieLabels = [...top10.map(c => c.nombre.substring(0, 20))];
    if (otrosTotal > 0) {
        pieData.push(otrosTotal);
        pieLabels.push('Otros (' + otros.length + ')');
    }

    charts.ingresosPie = new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: pieLabels,
            datasets: [{
                data: pieData,
                backgroundColor: COLORES.palette.concat(['#9ca3af'])
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Distribucion por Cliente'
                },
                legend: {
                    position: 'right',
                    labels: {
                        boxWidth: 12,
                        font: { size: 10 }
                    }
                }
            }
        }
    });

    // Line Chart mensual con area
    const ctxBar = document.getElementById('chart-ingresos-bar').getContext('2d');
    if (charts.ingresosBar) charts.ingresosBar.destroy();

    charts.ingresosBar = new Chart(ctxBar, {
        type: 'line',
        data: {
            labels: MESES,
            datasets: [{
                label: 'Ingresos Mensuales',
                data: d.ingresos.totalMensual,
                borderColor: COLORES.advertencia,
                backgroundColor: COLORES.advertencia + '20',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    ticks: {
                        callback: value => value.toLocaleString('es-GT')
                    }
                }
            }
        }
    });
}

// Costos
function renderizarCostos() {
    const d = datosPresupuesto;

    document.getElementById('badge-margen').textContent = 'Margen: ' + d.margenBruto.porcentaje.toFixed(1) + '%';

    // Tabla de costos
    const tbody = document.getElementById('costos-body');
    tbody.innerHTML = d.costos.detalle.map(c => `
        <tr>
            <td>${c.nombre}</td>
            <td class="number">${formatoMoneda(c.total)}</td>
            <td class="number">${(c.total / d.costos.totalAnual * 100).toFixed(1)}%</td>
        </tr>
    `).join('') + `
        <tr class="total-row">
            <td><strong>Total Costos</strong></td>
            <td class="number"><strong>${formatoMoneda(d.costos.totalAnual)}</strong></td>
            <td class="number"><strong>100%</strong></td>
        </tr>
    `;

    // Grafico Doughnut - Por Categoria
    const ctxPie = document.getElementById('chart-costos-pie').getContext('2d');
    if (charts.costosPie) charts.costosPie.destroy();

    charts.costosPie = new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: d.costos.detalle.map(c => c.nombre),
            datasets: [{
                data: d.costos.detalle.map(c => c.total),
                backgroundColor: [COLORES.peligro, COLORES.advertencia, COLORES.info]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    // Grafico Linea - Costos Mensuales
    const ctxLine = document.getElementById('chart-costos-line').getContext('2d');
    if (charts.costosLine) charts.costosLine.destroy();

    charts.costosLine = new Chart(ctxLine, {
        type: 'line',
        data: {
            labels: MESES,
            datasets: [{
                label: 'Costos Mensuales',
                data: d.costos.totalMensual,
                borderColor: COLORES.advertencia,
                backgroundColor: COLORES.advertencia + '20',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    ticks: {
                        callback: value => value.toLocaleString('es-GT')
                    }
                }
            }
        }
    });
}

// OPEX
function renderizarOPEX() {
    const d = datosPresupuesto;

    document.getElementById('badge-opex').textContent = formatoMoneda(d.opex.totalAnual);

    // Calcular totales por categoria
    const totalConsultores = d.opex.consultores.reduce((s, g) => s + g.total, 0);
    const totalSoftware = d.opex.software.reduce((s, g) => s + g.total, 0);
    const totalOtros = d.opex.otros.reduce((s, g) => s + g.total, 0);

    // Grafico por categoria
    const ctxCat = document.getElementById('chart-opex-categoria').getContext('2d');
    if (charts.opexCategoria) charts.opexCategoria.destroy();

    charts.opexCategoria = new Chart(ctxCat, {
        type: 'doughnut',
        data: {
            labels: ['Consultores', 'Software', 'Otros'],
            datasets: [{
                data: [totalConsultores, totalSoftware, totalOtros],
                backgroundColor: [COLORES.primario, COLORES.secundario, COLORES.advertencia]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    // Grafico mensual
    const ctxMensual = document.getElementById('chart-opex-mensual').getContext('2d');
    if (charts.opexMensual) charts.opexMensual.destroy();

    charts.opexMensual = new Chart(ctxMensual, {
        type: 'line',
        data: {
            labels: MESES,
            datasets: [{
                label: 'OPEX Mensual',
                data: d.opex.totalMensual,
                borderColor: COLORES.advertencia,
                backgroundColor: COLORES.advertencia + '20',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    ticks: {
                        callback: value => value.toLocaleString('es-GT')
                    }
                }
            }
        }
    });

    // Tabla detalle OPEX
    const tbody = document.getElementById('opex-body');
    const todosOPEX = [...d.opex.consultores, ...d.opex.software, ...d.opex.otros].sort((a, b) => b.total - a.total);

    tbody.innerHTML = todosOPEX.map(g => `
        <tr>
            <td>${g.nombre}</td>
            <td><span class="badge-cat">${g.categoria}</span></td>
            <td class="number">${formatoMoneda(g.total)}</td>
            <td class="number">${formatoMoneda(g.total / 12)}</td>
        </tr>
    `).join('') + `
        <tr class="total-row">
            <td colspan="2"><strong>Total OPEX</strong></td>
            <td class="number"><strong>${formatoMoneda(d.opex.totalAnual)}</strong></td>
            <td class="number"><strong>${formatoMoneda(d.opex.totalAnual / 12)}</strong></td>
        </tr>
    `;
}

// Rankings
function renderizarRankings() {
    const d = datosPresupuesto;

    // Top 10 Clientes
    const listaClientes = document.getElementById('ranking-clientes');
    const top10Clientes = d.ingresos.clientes.slice(0, 10);
    const maxCliente = top10Clientes[0]?.total || 1;

    listaClientes.innerHTML = top10Clientes.map((c, i) => `
        <li class="ranking-item">
            <span class="ranking-position ${i < 3 ? 'top-3' : ''}">${i + 1}</span>
            <div class="ranking-info">
                <div class="ranking-name">${c.nombre}</div>
                <div class="ranking-bar">
                    <div class="ranking-bar-fill" style="width: ${(c.total / maxCliente * 100)}%"></div>
                </div>
            </div>
            <div class="ranking-value">
                ${formatoMonedaCorto(c.total)}
                <div class="ranking-percent">${(c.total / d.ingresos.totalAnual * 100).toFixed(1)}%</div>
            </div>
        </li>
    `).join('');

    // Top 10 Gastos
    const listaGastos = document.getElementById('ranking-gastos');
    const top10Gastos = d.gastos.slice(0, 10);
    const maxGasto = top10Gastos[0]?.total || 1;
    const totalGastos = d.costos.totalAnual + d.opex.totalAnual;

    listaGastos.innerHTML = top10Gastos.map((g, i) => `
        <li class="ranking-item">
            <span class="ranking-position ${i < 3 ? 'top-3' : ''}">${i + 1}</span>
            <div class="ranking-info">
                <div class="ranking-name">${g.nombre}</div>
                <div class="ranking-bar">
                    <div class="ranking-bar-fill" style="width: ${(g.total / maxGasto * 100)}%; background: linear-gradient(90deg, ${COLORES.peligro}, ${COLORES.advertencia});"></div>
                </div>
            </div>
            <div class="ranking-value">
                ${formatoMonedaCorto(g.total)}
                <div class="ranking-percent">${(g.total / totalGastos * 100).toFixed(1)}%</div>
            </div>
        </li>
    `).join('');
}

// ============================================
// NAVEGACION
// ============================================
function inicializarNavegacion() {
    const tabs = document.querySelectorAll('.nav-tab');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const section = tab.dataset.section;

            // Actualizar tabs activos
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Mostrar/ocultar secciones
            const secciones = {
                'all': ['kpis', 'pl', 'ventas', 'pl-consolidado', 'ingresos', 'costos', 'opex', 'rankings'],
                'kpis': ['kpis'],
                'pl': ['pl'],
                'ventas': ['ventas'],
                'pl-consolidado': ['pl-consolidado'],
                'ingresos': ['ingresos'],
                'costos': ['costos'],
                'opex': ['opex'],
                'rankings': ['rankings']
            };

            const visibles = secciones[section] || secciones['all'];

            document.querySelectorAll('[id^="section-"]').forEach(sec => {
                const id = sec.id.replace('section-', '');
                sec.style.display = visibles.includes(id) ? 'block' : 'none';
            });
        });
    });
}

// ============================================
// VENTAS DE PRODUCTOS
// ============================================
function inicializarVentas() {
    // Agregar event listeners a los inputs de ventas
    for (let i = 0; i < 12; i++) {
        const input = document.getElementById(`venta-${i}`);
        if (input) {
            input.addEventListener('input', function() {
                actualizarVentas();
            });
            input.addEventListener('change', function() {
                guardarVentas();
            });
        }
    }
}

function actualizarVentas() {
    // Leer valores de inputs
    for (let i = 0; i < 12; i++) {
        const input = document.getElementById(`venta-${i}`);
        ventasProductos[i] = parseFloat(input?.value) || 0;
    }

    // Calcular costos y margenes
    const costoVentas = ventasProductos.map(v => v * (1 - MARGEN_PRODUCTOS));
    const margenProductos = ventasProductos.map(v => v * MARGEN_PRODUCTOS);

    // Actualizar celdas de costo
    for (let i = 0; i < 12; i++) {
        document.getElementById(`costo-${i}`).textContent = formatoDecimal(costoVentas[i]);
        document.getElementById(`margen-prod-${i}`).textContent = formatoDecimal(margenProductos[i]);
    }

    // Actualizar totales
    const totalVentas = sumar(ventasProductos);
    const totalCosto = sumar(costoVentas);
    const totalMargen = sumar(margenProductos);

    document.getElementById('total-ventas').textContent = formatoDecimal(totalVentas);
    document.getElementById('total-costo-ventas').textContent = formatoDecimal(totalCosto);
    document.getElementById('total-margen-productos').textContent = formatoDecimal(totalMargen);

    // Renderizar graficos de ventas
    renderizarGraficosVentas();

    // Actualizar P&L consolidado si hay datos del presupuesto
    if (datosPresupuesto) {
        renderizarPLConsolidado();
    }
}

function renderizarGraficosVentas() {
    const totalVentas = sumar(ventasProductos);
    const costoVentas = ventasProductos.map(v => v * (1 - MARGEN_PRODUCTOS));
    const margenProductos = ventasProductos.map(v => v * MARGEN_PRODUCTOS);

    // Grafico Doughnut - Distribucion
    const ctxPie = document.getElementById('chart-ventas-pie');
    if (ctxPie) {
        if (charts.ventasPie) charts.ventasPie.destroy();

        charts.ventasPie = new Chart(ctxPie.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Costo de Ventas (70%)', 'Margen Bruto (30%)'],
                datasets: [{
                    data: [sumar(costoVentas), sumar(margenProductos)],
                    backgroundColor: [COLORES.peligro, COLORES.exito]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    // Grafico Linea - Ventas Mensuales
    const ctxLine = document.getElementById('chart-ventas-line');
    if (ctxLine) {
        if (charts.ventasLine) charts.ventasLine.destroy();

        charts.ventasLine = new Chart(ctxLine.getContext('2d'), {
            type: 'line',
            data: {
                labels: MESES,
                datasets: [{
                    label: 'Ventas Mensuales',
                    data: ventasProductos,
                    borderColor: COLORES.advertencia,
                    backgroundColor: COLORES.advertencia + '20',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        ticks: {
                            callback: value => value.toLocaleString('es-GT')
                        }
                    }
                }
            }
        });
    }
}

function guardarVentas() {
    localStorage.setItem('ventasProductos2026', JSON.stringify(ventasProductos));
}

function cargarVentasGuardadas() {
    const datos = localStorage.getItem('ventasProductos2026');
    if (datos) {
        try {
            ventasProductos = JSON.parse(datos);
            // Actualizar inputs
            for (let i = 0; i < 12; i++) {
                const input = document.getElementById(`venta-${i}`);
                if (input) {
                    input.value = ventasProductos[i];
                }
            }
            actualizarVentas();
        } catch (e) {
            console.error('Error cargando ventas guardadas:', e);
        }
    }
}

// ============================================
// P&L CONSOLIDADO
// ============================================
function renderizarPLConsolidado() {
    if (!datosPresupuesto) return;

    const d = datosPresupuesto;
    const costoVentas = ventasProductos.map(v => v * (1 - MARGEN_PRODUCTOS));
    const margenProductos = ventasProductos.map(v => v * MARGEN_PRODUCTOS);

    // Calcular totales consolidados
    const ingresosConsolidadosMensual = d.ingresos.totalMensual.map((v, i) => v + ventasProductos[i]);
    const costosConsolidadosMensual = d.costos.totalMensual.map((v, i) => v + costoVentas[i]);
    const margenBrutoConsolidadoMensual = d.margenBruto.mensual.map((v, i) => v + margenProductos[i]);
    const resultadoConsolidadoMensual = margenBrutoConsolidadoMensual.map((v, i) => v - d.opex.totalMensual[i]);

    const totalIngresosConsolidado = sumar(ingresosConsolidadosMensual);
    const totalCostosConsolidado = sumar(costosConsolidadosMensual);
    const totalMargenBrutoConsolidado = sumar(margenBrutoConsolidadoMensual);
    const totalResultadoConsolidado = sumar(resultadoConsolidadoMensual);

    const margenBrutoPct = totalIngresosConsolidado > 0 ? (totalMargenBrutoConsolidado / totalIngresosConsolidado * 100) : 0;
    const margenOperativoPct = totalIngresosConsolidado > 0 ? (totalResultadoConsolidado / totalIngresosConsolidado * 100) : 0;

    // Actualizar badge
    document.getElementById('badge-resultado-consolidado').textContent =
        `Resultado: ${formatoMoneda(totalResultadoConsolidado)}`;

    // Construir tabla
    const tbody = document.getElementById('pl-consolidado-body');
    const filas = [
        { concepto: '(+) Ingresos Recurrentes', datos: d.ingresos.totalMensual, total: d.ingresos.totalAnual, clase: '' },
        { concepto: '(+) Ventas de Productos', datos: ventasProductos, total: sumar(ventasProductos), clase: '' },
        { concepto: '(=) INGRESOS TOTALES', datos: ingresosConsolidadosMensual, total: totalIngresosConsolidado, clase: 'subtotal-row', style: 'background: #dcfce7;' },
        { concepto: '(-) Costos Recurrentes', datos: d.costos.totalMensual, total: d.costos.totalAnual, clase: '' },
        { concepto: '(-) Costo de Ventas (70%)', datos: costoVentas, total: sumar(costoVentas), clase: '' },
        { concepto: '(=) TOTAL COSTOS', datos: costosConsolidadosMensual, total: totalCostosConsolidado, clase: 'subtotal-row', style: 'background: #fee2e2;' },
        { concepto: `(=) MARGEN BRUTO (${margenBrutoPct.toFixed(1)}%)`, datos: margenBrutoConsolidadoMensual, total: totalMargenBrutoConsolidado, clase: 'subtotal-row', style: 'background: #dbeafe;' },
        { concepto: '(-) Gastos Operativos (OPEX)', datos: d.opex.totalMensual, total: d.opex.totalAnual, clase: '' },
        { concepto: `(=) RESULTADO NETO (${margenOperativoPct.toFixed(1)}%)`, datos: resultadoConsolidadoMensual, total: totalResultadoConsolidado, clase: 'total-row', style: totalResultadoConsolidado >= 0 ? 'background: #dcfce7;' : 'background: #fee2e2;' }
    ];

    tbody.innerHTML = filas.map(f => `
        <tr class="${f.clase}" style="${f.style || ''}">
            <td><strong>${f.concepto}</strong></td>
            ${f.datos.map(v => `<td class="number ${v < 0 ? 'negative' : ''}">${formatoMonedaCorto(v)}</td>`).join('')}
            <td class="number ${f.total < 0 ? 'negative' : ''}"><strong>${formatoMonedaCorto(f.total)}</strong></td>
        </tr>
    `).join('');

    // Renderizar graficos consolidados
    renderizarGraficosConsolidado(d, totalIngresosConsolidado, totalResultadoConsolidado, resultadoConsolidadoMensual);
}

function renderizarGraficosConsolidado(d, totalIngresos, totalResultado, resultadoMensual) {
    // Grafico Doughnut - Composicion de Ingresos
    const ctxPie = document.getElementById('chart-consolidado-pie');
    if (ctxPie) {
        if (charts.consolidadoPie) charts.consolidadoPie.destroy();

        charts.consolidadoPie = new Chart(ctxPie.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Ingresos Recurrentes', 'Ventas Productos'],
                datasets: [{
                    data: [d.ingresos.totalAnual, sumar(ventasProductos)],
                    backgroundColor: [COLORES.secundario, COLORES.exito]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    // Grafico Linea - Resultado Consolidado Mensual
    const ctxLine = document.getElementById('chart-consolidado-line');
    if (ctxLine) {
        if (charts.consolidadoLine) charts.consolidadoLine.destroy();

        charts.consolidadoLine = new Chart(ctxLine.getContext('2d'), {
            type: 'line',
            data: {
                labels: MESES,
                datasets: [{
                    label: 'Resultado Mensual',
                    data: resultadoMensual,
                    borderColor: COLORES.advertencia,
                    backgroundColor: COLORES.advertencia + '20',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        ticks: {
                            callback: value => value.toLocaleString('es-GT')
                        }
                    }
                }
            }
        });
    }
}

// ============================================
// UTILIDADES
// ============================================
function formatoMoneda(valor) {
    return valor.toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatoMonedaCorto(valor) {
    return valor.toLocaleString('es-GT', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Formato con todos los decimales para vista detallada
function formatoDecimal(valor) {
    if (valor === 0 || valor === null || valor === undefined) return '0.00';
    return valor.toLocaleString('es-GT', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function actualizarLastUpdate() {
    const fecha = localStorage.getItem('presupuesto2026_fecha');
    if (fecha) {
        const d = new Date(fecha);
        document.getElementById('lastUpdate').textContent =
            'Actualizado: ' + d.toLocaleDateString('es-GT') + ' ' + d.toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit' });
    }
}

function cargarDatosGuardados() {
    const datos = localStorage.getItem('presupuesto2026');
    if (datos) {
        try {
            datosPresupuesto = JSON.parse(datos);
            const uploadZone = document.getElementById('uploadZone');
            uploadZone.classList.add('loaded');
            uploadZone.innerHTML = `
                <div class="upload-icon">&#9989;</div>
                <h3>Datos cargados desde cache</h3>
                <p>Haz clic para actualizar con un nuevo archivo</p>
                <input type="file" id="fileInput" accept=".xlsx,.xls" style="display: none;">
            `;

            // Re-vincular el evento del input
            document.getElementById('fileInput').addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) procesarArchivo(file);
            });

            actualizarLastUpdate();
            renderizarDashboard();
        } catch (e) {
            console.error('Error cargando datos guardados:', e);
        }
    }
}
