import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests
import unicodedata
import re
from collections import Counter
import streamlit.components.v1 as components

# ==========================================
# 1. CONFIGURACIÓN, PESOS Y UMBRALES (SAGRADOS)
# ==========================================
st.set_page_config(page_title="APA - ITSON", layout="wide")

PESO_CORE   = 0.40  
PESO_CITAS  = 0.30  
PESO_LIDER  = 0.20  
PESO_HINDEX = 0.50  

UMBRAL_ALTO = 0.70  
UMBRAL_MED  = 0.40  

EMAIL_FIXED = "lcsia.estudiantes@gmail.com"
headers = {'User-Agent': f'mailto:{EMAIL_FIXED}'}
anio_actual = 2026 
anio_inicio_auto = anio_actual - 6 
STOP_WORDS = [
    # --- INGLÉS (Singular y Plural) ---
    "the", "and", "for", "with", "from", "using", "study", "studies", "analysis", 
    "effect", "effects", "between", "during", "towards", "under", "through", 
    "within", "across", "among", "about", "into", "over", "after", "before", 
    "their", "such", "than", "which", "that", "those", "these", "whose", "when",
    "where", "while", "how", "many", "some", "very", "most", "each", "both",
    
    # --- ESPAÑOL (Singular y Plural) ---
    "el", "la", "lo", "los", "las", "un", "una", "uno", "unos", "unas", "de", 
    "del", "en", "con", "por", "para", "sobre", "entre", "su", "sus", "como", 
    "esta", "este", "esto", "estos", "estas", "esa", "ese", "eso", "esos", 
    "esas", "que", "quien", "quienes", "cual", "cuales", "donde", "cuando", 
    "como", "pero", "sino", "aunque", "desde", "hasta", "hacia", "ante",
    
    # --- ACADÉMICAS BILINGÜES (Singular y Plural) ---
    "study", "studies", "estudio", "estudios",
    "analysis", "analyses", "analisis",
    "effect", "effects", "efecto", "efectos",
    "relation", "relations", "relationship", "relacion", "relaciones",
    "use", "using", "uso", "usos", "utilizacion",
    "evaluation", "evaluations", "evaluacion", "evaluaciones",
    "comparative", "comparison", "comparativo", "comparativa", "comparacion",
    "influence", "influences", "influencia", "influencias",
    "application", "applications", "aplicacion", "aplicaciones",
    "review", "reviews", "revision", "revisiones",
    "case", "cases", "caso", "casos",
    "result", "results", "resultado", "resultados",
    "evidence", "evidencia", "evidencias",
    "approach", "approaches", "enfoque", "enfoques",
    "impact", "impacts", "impacto", "impactos",
    "factor", "factors", "factor", "factores",
    "role", "roles", "papel", "rol", "roles",
    "level", "levels", "nivel", "niveles"
]

# ==========================================
# 2. FUNCIONES DE PROCESAMIENTO
# ==========================================
def normalizar_extremo(texto):
    if not texto: return []
    texto = texto.replace('ı', 'i').replace('−', '-')
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = texto.lower()
    palabras = re.findall(r'\b[a-z0-9]+(?:-[a-z0-9]+)*\b', texto)
    return [p for p in palabras if len(p) > 2]

@st.cache_data(ttl=3600)
def obtener_metricas_revista(source_id):
    """Consulta los datos maestros de la revista si no vienen en el objeto obra"""
    if not source_id: return 0.0, False
    try:
        url = f"https://api.openalex.org/sources/{source_id.split('/')[-1]}"
        r = requests.get(url, headers=headers).json()
        tw = r.get('works_count', 0)
        tc = r.get('cited_by_count', 0)
        is_core = r.get('is_core', False)
        promedio = tc / tw if tw > 0 else 0
        return promedio, is_core
    except:
        return 0.0, False

def analizar_grupo(articulos, lista_ids_autor):
    citas_lista = sorted([o.get('cited_by_count', 0) for o in articulos], reverse=True)
    h_index = sum(1 for i, c in enumerate(citas_lista) if c >= i + 1)
    primer_autor, correspondencia = 0, 0
    rev_oa, rev_pago = 0, 0
    topics_list, words_list, registros_paperdata = [], [], []
    n_calidad_real = 0

    for obra in articulos:
        es_primer, es_corr = "", ""
        aut_objs = obra.get('authorships', [])
        autores_full = [a.get('author', {}).get('display_name') for a in aut_objs]
        num_citas_art = obra.get('cited_by_count', 0)
        
        for auth in aut_objs:
            curr_id = auth.get('author', {}).get('id')
            if curr_id in lista_ids_autor:
                if auth.get('author_position') == 'first': 
                    primer_autor, es_primer = primer_autor + 1, "X"
                if auth.get('is_corresponding'): 
                    correspondencia, es_corr = correspondencia + 1, "X"
        
        for t in obra.get('topics', []):
            if t.get('field') and t['field'].get('display_name'):
                topics_list.append(t['field']['display_name'])
        
        d_name = obra.get('display_name')
        if d_name: 
            words_list.extend([w for w in normalizar_extremo(d_name) if w not in STOP_WORDS])
        
        # --- LÓGICA DE FILTRO REFORZADA ---
        src_data = (obra.get('primary_location', {}) or {}).get('source', {}) or {}
        source_id = src_data.get('id')
        
        # Intentamos obtener del objeto actual
        tw = src_data.get('works_count')
        tc = src_data.get('cited_by_count')
        is_core_api = src_data.get('is_core', False)

        # Si los datos vienen vacíos (problema detectado), consultamos la fuente real
        if tw is None or tw == 0:
            promedio_revista, is_core_api = obtener_metricas_revista(source_id)
        else:
            promedio_revista = tc / tw if tw > 0 else 0
        
        # FILTRO FINAL
        es_alta_calidad = is_core_api and (promedio_revista >= 2.0)

        if es_alta_calidad:
            n_calidad_real += 1
        
        if (obra.get('open_access', {}).get('oa_status') in ['gold', 'diamond']): rev_oa += 1
        else: rev_pago += 1

        registros_paperdata.append({
            'Year': obra.get('publication_year'),
            'Authors': ", ".join(autores_full),
            'Title': obra.get('display_name'),
            'Journal': src_data.get('display_name', 'N/A'),
            'Citations': num_citas_art,
            '1st': es_primer,
            'Corr.': es_corr,
            'High-Qual': "X" if es_alta_calidad else "",
            'DOI': (obra.get('doi') or "").replace("https://doi.org/", "")
        })

    return {
        'n': len(articulos), 
        'n_calidad': n_calidad_real,
        'h': h_index, 
        'citas': sum(citas_lista), 
        '1er': primer_autor, 
        'corr': correspondencia,
        'rev_oa': rev_oa, 
        'rev_pago': rev_pago, 
        'top_temas': ([t for t, c in Counter(topics_list).most_common(3)] + [" "]*3)[:3],
        'top_words': ([w for w, c in Counter(words_list).most_common(3)] + [" "]*3)[:3],
        'paper_list': registros_paperdata
    }

def calcular_ide(res_t, res_c):
    if res_t['n'] == 0: return 0.0
    C = res_t['n_calidad'] / res_t['n']
    citas_calidad = sum(p['Citations'] for p in res_t['paper_list'] if p['High-Qual'] == "X")
    T = citas_calidad / res_t['citas'] if res_t['citas'] > 0 else 0
    L = (res_t['1er'] + res_t['corr']) / (2 * res_t['n'])
    H = res_t['h'] / res_t['n']
    ide = (PESO_CORE * C) + (PESO_CITAS * T) + (PESO_LIDER * L) + (PESO_HINDEX * H)
    return round(ide, 3)

# ==========================================
# 3. INTERFAZ: BÚSQUEDA
# ==========================================
col_tit, col_logo = st.columns([6, 1])
with col_logo:
    try: st.image("Logo.png", use_container_width=True)
    except: pass
with col_tit:
    st.markdown('<h1 style="font-size: 38px; margin-bottom: 0px;">Academic Performance Auditor</h1>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 18px; color: #5E5E5E; font-style: italic;">By Social Behavior and Artificial Intelligence Laboratory & Sonora Institute of Technology </p>', unsafe_allow_html=True)

nombre_buscar = st.text_input("Researcher Name:", value="Laurent Avila Chauvet")
solo_reciente = st.toggle("Recent Impact Analysis (Last 6 Years)", value=True)

download_placeholder = st.empty()

if st.button("Search"):
    url_bus = f"https://api.openalex.org/authors?filter=display_name.search:{nombre_buscar}&per_page=20"
    resp = requests.get(url_bus, headers=headers).json()
    if resp.get('results'):
        datos_tabla = [{"Select": i==0, "ID_OpenAlex": res['id'], "Full Name": res['display_name'], "Institution": (res.get('last_known_institutions') or [{'display_name':'Unknown'}])[0]['display_name']} for i, res in enumerate(resp['results'])]
        st.session_state['df_resultados'] = pd.DataFrame(datos_tabla)
        st.session_state['mostrar_tabla'] = True

st.markdown("---")

if st.session_state.get('mostrar_tabla'):
    edited_df = st.data_editor(st.session_state['df_resultados'], hide_index=True, use_container_width=True, column_config={"ID_OpenAlex": None}, key="editor_autores")
    if st.button("Confirm Selection and Proceed"):
        sel = edited_df[edited_df["Select"] == True]
        st.session_state['ids_confirmados'] = sel["ID_OpenAlex"].tolist()
        st.session_state['nombres_confirmados'] = sel["Full Name"].tolist()
        st.session_state['mostrar_tabla'] = False
        st.rerun()

# ==========================================
# 4. REPORTE FINAL
# ==========================================
if 'ids_confirmados' in st.session_state and not st.session_state.get('mostrar_tabla'):
    with st.spinner("Analyzing bibliographic data..."):
        ids_autor = st.session_state['ids_confirmados']
        investigador_raw = st.session_state['nombres_confirmados'][0]
        obras = []
        for ida in ids_autor:
            r = requests.get(f"https://api.openalex.org/works?filter=author.id:{ida},type:article&per_page=200", headers=headers).json()
            obras.extend(r.get('results', []))

        art_base = [o for o in obras if not solo_reciente or (anio_inicio_auto <= o.get('publication_year', 0) <= anio_actual)]
        res_t = analizar_grupo(art_base, ids_autor)
        
        art_solo_calidad = [o for o in art_base if any(p['Title'] == o['display_name'] and p['High-Qual'] == "X" for p in res_t['paper_list'])]
        res_c = analizar_grupo(art_solo_calidad, ids_autor)
        
        v_ide = calcular_ide(res_t, res_c)
        status_text = "High Impact" if v_ide >= UMBRAL_ALTO else "Consolidated" if v_ide >= UMBRAL_MED else "Low Impact"

        paper_df = pd.DataFrame(res_t['paper_list']).sort_values(by=['Year', 'Citations'], ascending=[False, False])
        csv_data = paper_df.to_csv(index=False).encode('utf-8')

    download_placeholder.download_button(label="Download Publication List", data=csv_data, file_name=f"Publications_{investigador_raw.replace(' ','_')}.csv", mime='text/csv')

    # --- DASHBOARD ---
    st.write(" ")
    B_1_1, B_1_2, _ = st.columns([2.5, 2, 1])
    B_1_1.title(st.session_state['nombres_confirmados'][0])
    B_1_1.write(f"Period: {'Last 6 Years' if solo_reciente else 'All time'}") 
    B_1_2.write(""); B_1_2.subheader(f"| {status_text}")

    st.markdown(" ")
    B_2_1, B_2_2, B_2_3, B_2_4, _ = st.columns([1, 1, 1, 1, 6])
    B_2_1.metric("H-Index", res_t['h'])
    B_2_2.metric("Total Works", res_t['n'])
    B_2_3.metric("Citations", res_t['citas'])
    B_2_4.metric("Impact (IDE)", f"{v_ide:.3f}")

    # Donas
    st.write(" ")
    B_3_1, B_3_2, B_3_3 = st.columns(3)
    n_high = res_t['n_calidad']
    c_high = sum(p['Citations'] for p in res_t['paper_list'] if p['High-Qual'] == "X")
    
    for col, tit, lbl, val, clr, tot in zip([B_3_1, B_3_2, B_3_3], ["Articles", "Citations", "Publication Model"],
        [['High-quality', 'Low-quality'], ['High-quality', 'Low-quality'], ['Open Open Access', 'Subscription/Hybrid']],
        [[n_high, res_t['n']-n_high], [c_high, res_t['citas']-c_high], [res_t['rev_oa'], res_t['rev_pago']]],
        [['#28a745', '#dc3545'], ['#28a745', '#dc3545'], ['#FFD700', '#2F4F4F']], [res_t['n'], res_t['citas'], res_t['n']]):
        fig = go.Figure(data=[go.Pie(labels=lbl, values=val, hole=.6, marker_colors=clr)])
        fig.update_layout(annotations=[dict(text=f'Total<br>{tot}', x=0.5, y=0.5, font_size=20, showarrow=False)], height=250, margin=dict(t=30,b=0,l=0,r=0))
        col.subheader(tit); col.plotly_chart(fig, use_container_width=True)

    # Liderazgo
    st.write(" "); B_4_1, B_4_2 = st.columns(2)
    for col, tit, n, v1, v2 in zip([B_4_1, B_4_2], ["High-quality Journals", "Low-quality Journals"],
                                   [n_high, res_t['n']-n_high], [res_c['1er'], res_t['1er']-res_c['1er']], [res_c['corr'], res_t['corr']-res_c['corr']]):
        v3 = max(0, n - v1 - v2)
        fig = go.Figure(data=[go.Pie(labels=['First Author', 'Corresponding Author', 'Co-author'], values=[v1, v2, v3], hole=.6, marker_colors=['#003366', '#336699', '#A9A9A9'])])
        fig.update_layout(annotations=[dict(text=f'Total<br>{n}', x=0.5, y=0.5, font_size=20, showarrow=False)], height=250, margin=dict(t=30,b=0,l=0,r=0))
        col.subheader(tit); col.plotly_chart(fig, use_container_width=True)

    # Áreas y Keywords
    st.write(" "); B_5_1, B_5_2 = st.columns(2)
    B_5_1.subheader("Scientific Area (High-quality)"); B_5_1.write(pd.DataFrame(res_c['top_temas']).to_html(index=False, header=False, classes='table'), unsafe_allow_html=True)
    B_5_2.subheader("Scientific Area (Low-quality)"); B_5_2.write(pd.DataFrame(res_t['top_temas']).to_html(index=False, header=False, classes='table'), unsafe_allow_html=True)
    st.write(" "); B_6_1, B_6_2 = st.columns(2)
    B_6_1.subheader("Top Keywords (High-quality)"); B_6_1.write(pd.DataFrame(res_c['top_words']).to_html(index=False, header=False, classes='table'), unsafe_allow_html=True)
    B_6_2.subheader("Top Keywords (Low-quality)"); B_6_2.write(pd.DataFrame(res_t['top_words']).to_html(index=False, header=False, classes='table'), unsafe_allow_html=True)

    # Tabla Final
    st.markdown("---")
    st.subheader("Published Articles")
    st.dataframe(paper_df, use_container_width=True, hide_index=True, height=(len(paper_df)+1)*36, 
                 column_config={"Title": st.column_config.TextColumn("Title", width="large"), "Authors": st.column_config.TextColumn("Authors", width="medium")})

st.markdown("<style>table { width: 100%; border-bottom: 1px solid #f0f2f6; font-size: 1.1rem; }</style>", unsafe_allow_html=True)





