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
    if not source_id: return 0.0, False
    try:
        sid = source_id.split('/')[-1]
        url = f"https://api.openalex.org/sources/{sid}"
        r = requests.get(url, headers=headers).json()
        
        tw = r.get('works_count', 0)
        tc = r.get('cited_by_count', 0)
        is_core = r.get('is_core', False)
        
        promedio = tc / tw if tw > 0 else 0
        return promedio, is_core
    except:
        return 0.0, False

def analizar_grupo(articulos, lista_ids_autor):
    primer_autor, correspondencia = 0, 0
    rev_oa, rev_pago = 0, 0
    topics_list, words_list, registros_paperdata = [], [], []
    n_calidad_real = 0
    n_endogamia, n_externo = 0, 0
    citas_filtradas = []
    
    lista_ids_limpia = [str(i).split('/')[-1] for i in lista_ids_autor if i]

    for obra in articulos:
        prim_loc = obra.get('primary_location') or {}
        source = prim_loc.get('source') or {}
        source_id = source.get('id')
        journal_name = source.get('display_name') or ""
        
        # --- Lógica de Endogamia ---
        inst_investigador = set()
        todas_inst_obra = set()
        
        for auth in obra.get('authorships', []):
            author_ref = auth.get('author', {}) or {}
            curr_id = str(author_ref.get('id', '')).split('/')[-1]
            insts = auth.get('institutions', []) or []
            for inst in insts:
                inst_id = inst.get('id')
                if inst_id:
                    todas_inst_obra.add(inst_id)
                    if curr_id in lista_ids_limpia:
                        inst_investigador.add(inst_id)

        if not todas_inst_obra:
            es_externo = False
            p_ext = 0
        else:
            ins_externas = todas_inst_obra - inst_investigador
            es_externo = len(ins_externas) > 0
            p_ext = (len(ins_externas) / len(todas_inst_obra)) * 100

        if es_externo: n_externo += 1
        else: n_endogamia += 1

        # --- Lógica de Calidad ---
        tw = source.get('works_count', 0)
        tc = source.get('cited_by_count', 0)
        if not source_id or not journal_name:
            es_alta_calidad = False
        else:
            if not tw or tw == 0:
                promedio_revista, is_core = obtener_metricas_revista(source_id)
            else:
                promedio_revista = tc / tw if tw > 0 else 0
                is_core = source.get('is_core', False)
            es_alta_calidad = is_core or promedio_revista > 3

        if es_alta_calidad: n_calidad_real += 1

        # --- Lógica de Autoría y Citas ---
        num_citas_art = obra.get('cited_by_count', 0)
        citas_filtradas.append(num_citas_art)
        aut_objs = obra.get('authorships', [])
        autores_full = [a.get('author', {}).get('display_name') for a in aut_objs]
        
        es_p, es_c = "", ""
        for auth in aut_objs:
            a_id = str(auth.get('author', {}).get('id', '')).split('/')[-1]
            if a_id in lista_ids_limpia:
                if auth.get('author_position') == 'first':
                    primer_autor += 1
                    es_p = "X"
                if auth.get('is_corresponding'):
                    correspondencia += 1
                    es_c = "X"

        # --- Open Access ---
        oa_status = obra.get('open_access', {}).get('oa_status')
        if oa_status in ['diamond', 'green', 'closed']:
            rev_oa += 1
            author_cost = "No APC"
        else:
            rev_pago += 1
            author_cost = "APC Paid"

        d_name = obra.get('display_name') or ""
        words_list.extend([w for w in normalizar_extremo(d_name) if w not in STOP_WORDS])
        for t in obra.get('topics', []):
            if t.get('field'): topics_list.append(t['field'].get('display_name'))

        registros_paperdata.append({
            'Year': obra.get('publication_year'),
            'Authors': ", ".join(autores_full),
            'Title': d_name,
            'Journal': journal_name if journal_name else "Unidentified Source",
            'Citations': num_citas_art,
            '1st': es_p,
            'Corr.': es_c,
            'High-Qual': "X" if es_alta_calidad else "",
            'Ext_Colab_%': round(p_ext, 1), # Se queda solo el porcentaje numérico
            'Author_Cost': author_cost,
            'DOI': (obra.get('doi') or "").replace("https://doi.org/", "")
        })

    citas_lista = sorted(citas_filtradas, reverse=True)
    h_index = sum(1 for i, c in enumerate(citas_lista) if c >= i + 1)

    return {
        'n': len(registros_paperdata), 'n_calidad': n_calidad_real, 'h': h_index,
        'citas': sum(citas_filtradas), '1er': primer_autor, 'corr': correspondencia,
        'rev_oa': rev_oa, 'rev_pago': rev_pago, 'n_endo': n_endogamia, 'n_ext': n_externo,
        'top_temas_global': [t for t, c in Counter(topics_list).most_common(5)],
        'top_words_global': [w for w, c in Counter(words_list).most_common(5)],
        'paper_list': registros_paperdata
    }

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
solo_reciente = st.toggle("Recent Impact Analysis (2020-2026)", value=True)

download_placeholder = st.empty()

if st.button("Search"):
    url_bus = f"https://api.openalex.org/authors?filter=display_name.search:{nombre_buscar}&per_page=20"
    resp = requests.get(url_bus, headers=headers).json()# Modifica esta parte en la sección 3 (INTERFAZ: BÚSQUEDA)
    if resp.get('results'):
        datos_tabla = [
            {
                "Select": i == 0, 
                "ID_OpenAlex": res['id'], 
                "Full Name": res['display_name'], 
                "Institution": (res.get('last_known_institutions') or [{'display_name':'Unknown'}])[0]['display_name'],
                "H-Index (OA)": res.get('summary_stats', {}).get('h_index', 0) # <--- Agregamos esto
            } for i, res in enumerate(resp['results'])
        ]
        st.session_state['df_resultados'] = pd.DataFrame(datos_tabla)
        st.session_state['mostrar_tabla'] = True

st.markdown("---")

if st.session_state.get('mostrar_tabla'):
    edited_df = st.data_editor(st.session_state['df_resultados'], hide_index=True, use_container_width=True, column_config={"ID_OpenAlex": None}, key="editor_autores")
    if st.button("Confirm Selection and Proceed"):
        sel = edited_df[edited_df["Select"] == True]
        st.session_state['ids_confirmados'] = sel["ID_OpenAlex"].tolist()
        st.session_state['nombres_confirmados'] = sel["Full Name"].tolist()
        # Guardamos el H-Index de OpenAlex del autor seleccionado
        st.session_state['h_index_oa'] = sel["H-Index (OA)"].iloc[0] if not sel.empty else 0
        st.session_state['mostrar_tabla'] = False
        st.rerun()

# ==========================================
# 4. REPORTE FINAL
# ==========================================
if 'ids_confirmados' in st.session_state and not st.session_state.get('mostrar_tabla'):
    with st.spinner("Analyzing bibliographic data..."):
        ids_autor = st.session_state['ids_confirmados']
        investigador_raw = st.session_state['nombres_confirmados'][0]
        
        obras_sucias = []
        PREPRINT_SERVERS = ["arxiv", "biorxiv", "medrxiv", "ssrn", "researchsquare", "preprints.org", "chemrxiv", "psyarxiv", "socarxiv", "zenodo"]
        
        for ida in ids_autor:
            r = requests.get(f"https://api.openalex.org/works?filter=author.id:{ida},type:article&per_page=200", headers=headers).json()
            obras_sucias.extend(r.get('results', []))

        obras = []
        for o in obras_sucias:
            source = (o.get('primary_location', {}) or {}).get('source') or {}
            j_name = (source.get('display_name') or "").lower()
            s_type = source.get('type') or ""
            
            if s_type != 'repository' and not any(p in j_name for p in PREPRINT_SERVERS):
                obras.append(o)

        art_base = [o for o in obras if not solo_reciente or (anio_inicio_auto <= o.get('publication_year', 0) <= anio_actual)]
        
        if not art_base:
            st.warning("No articles found for the selected period (excluding preprints).")
            st.stop()

        res_t = analizar_grupo(art_base, ids_autor)
        
        art_solo_calidad = [o for o in art_base if any(p['Title'] == o['display_name'] and p['High-Qual'] == "X" for p in res_t['paper_list'])]
        res_c = analizar_grupo(art_solo_calidad, ids_autor)

        paper_df = pd.DataFrame(res_t['paper_list']).sort_values(by=['Year', 'Citations'], ascending=[False, False])
        csv_data = paper_df.to_csv(index=False).encode('utf-8')

    download_placeholder.download_button(label="Download Publication List", data=csv_data, file_name=f"Publications_{investigador_raw.replace(' ','_')}.csv", mime='text/csv')
    
    # --- DASHBOARD ---
    st.write(" ")
    B_1_1, B_1_2, _ = st.columns([2.5, 2, 1])
    B_1_1.title(st.session_state['nombres_confirmados'][0])
    B_1_1.write(f"Period: {'Last 6 Years' if solo_reciente else 'All time'}") 
    B_1_2.write("")
    # B_1_2.write(""); B_1_2.subheader(f"| {status_text}")

    st.markdown(" ")
    B_2_1, B_2_2, B_2_3, B_2_4, _ = st.columns([1, 1, 1, 1, 4])
    B_2_1.metric("H-Index (OA)", st.session_state.get('h_index_oa', 0))
    B_2_2.metric("H-Index", res_t['h'])
    B_2_3.metric("Total Works", res_t['n'])
    B_2_4.metric("Citations", res_t['citas'])

    # Donas
    st.write(" ")
    B_3_1, B_3_2, B_3_3 = st.columns(3)
    n_high = res_t['n_calidad']
    c_high = sum(p['Citations'] for p in res_t['paper_list'] if p['High-Qual'] == "X")
    
    for col, tit, lbl, val, clr, tot in zip([B_3_1, B_3_2, B_3_3], ["Articles", "Citations", "Articles Cost Model"],
        [["High-Impact Journals", "Standard Journals"], ["High-Impact Journals", "Standard Journals"], ['No APC (Free)', 'APC (Paid)']],
        [[n_high, res_t['n']-n_high], [c_high, res_t['citas']-c_high], [res_t['rev_oa'], res_t['rev_pago']]],
        [['#28a745', '#dc3545'], ['#28a745', '#dc3545'], ['#2F4F4F','#FFD700']], [res_t['n'], res_t['citas'], res_t['n']]):
        
        fig = go.Figure(data=[go.Pie(labels=lbl, values=val, hole=.6, marker_colors=clr)])
        fig.update_layout(annotations=[dict(text=f'Total<br>{tot}', x=0.5, y=0.5, font_size=20, showarrow=False)], height=250, margin=dict(t=30,b=0,l=0,r=0))
        col.subheader(tit); col.plotly_chart(fig, use_container_width=True)

    # Liderazgo
    st.write(" "); B_4_1, B_4_2, B_4_3 = st.columns(3)
    for col, tit, n, v1, v2, clr, lbl in zip(
        [B_4_1, B_4_2, B_4_3], 
        ["High-Impact Journals", "Standard Journals", "Networking"],
        [res_c['n'], res_t['n']-res_c['n'], res_t['n']], 
        [res_c['1er'], res_t['1er']-res_c['1er'], res_t['n_ext']], 
        [res_c['corr'], res_t['corr']-res_c['corr'], res_t['n_endo']],
        [['#003366', '#336699', '#A9A9A9'], ['#003366', '#336699', '#A9A9A9'], ['#27ae60', '#e74c3c', '#A9A9A9']],
        [['First Author', 'Corresponding Author', 'Co-author'], ['First Author', 'Corresponding Author', 'Co-author'], ['Cross-institutional', 'Inter-institutional', 'No-id']]
    ):
        v3 = max(0, n - v1 - v2)
        fig = go.Figure(data=[go.Pie(labels=lbl, values=[v1, v2, v3], hole=.6, marker_colors=clr)])
        fig.update_layout(annotations=[dict(text=f'Total<br>{n}', x=0.5, y=0.5, font_size=20, showarrow=False)], height=250, margin=dict(t=30,b=0,l=0,r=0))
        col.subheader(tit); col.plotly_chart(fig, use_container_width=True)

    # Áreas y Keywordsst.write(" ")
    st.write(" ")
    B_5_1, B_5_2 = st.columns(2)

    with B_5_1:
        st.subheader("Top Scientific Areas")
        df_temas = pd.DataFrame(res_t['top_temas_global'])
        st.write(df_temas.to_html(index=False, header=False, classes='table'), unsafe_allow_html=True)

    with B_5_2:
        st.subheader("Top Keywords")
        df_words = pd.DataFrame(res_t['top_words_global'])
        st.write(df_words.to_html(index=False, header=False, classes='table'), unsafe_allow_html=True)
        
# ==========================================
    # NUEVA SECCIÓN: TOP PUBLICACIONES (APA + CITAS)
    # ==========================================
    st.write(" ")
    st.subheader("Most Cited Publications")
    
    # Obtenemos las 3 más citadas
    top_papers = paper_df.nlargest(3, 'Citations')
    
    for i, (idx, row) in enumerate(top_papers.iterrows()):
        # --- Lógica para formatear Autores en APA ---
        raw_authors = row['Authors'].split(", ")
        apa_authors_list = []
        for auth in raw_authors:
            parts = auth.strip().split(" ")
            if len(parts) > 1:
                apellido = parts[-1]
                inicial = parts[0][0]
                apa_authors_list.append(f"{apellido}, {inicial}.")
            else:
                apa_authors_list.append(auth)
        
        if len(apa_authors_list) > 1:
            autores_apa = ", ".join(apa_authors_list[:-1]) + " & " + apa_authors_list[-1]
        else:
            autores_apa = apa_authors_list[0] if apa_authors_list else "Unknown"

        # --- Construcción de la Referencia ---
        año = row['Year']
        titulo = row['Title']
        revista = row['Journal']
        doi = row['DOI']
        citas = int(row['Citations'])
        doi_url = f"https://doi.org/{doi.replace('https://doi.org/', '')}"

        st.markdown(
            f"""
            <div style="margin-bottom: 20px; padding-left: 30px; text-indent: -30px; line-height: 1.6; font-family: 'Segoe UI', sans-serif;">
                {autores_apa} ({año}). {titulo}. 
                <em>{revista}</em>. <a href="{doi_url}" target="_blank" style="color: #0066cc; text-decoration: none;">{doi_url}</a> 
                <strong>({citas} citations)</strong>
            </div>
            """, 
            unsafe_allow_html=True
        )
    # Tabla Final
    st.markdown("---")
    st.subheader("Published Articles")
    st.dataframe(
        paper_df, 
        use_container_width=True, 
        hide_index=True, 
        height=(len(paper_df)+1)*34, 
        column_config={
            "Year": st.column_config.TextColumn("Year", width="small"),
            "Title": st.column_config.TextColumn("Title", width="large"), 
            "Authors": st.column_config.TextColumn("Authors", width="medium"),
            "Journal": st.column_config.TextColumn("Journal", width="medium"),
            "Citations": st.column_config.NumberColumn("Cites", width="small"),
            "1st": st.column_config.TextColumn("1st", width="small"),
            "Corr.": st.column_config.TextColumn("Corr.", width="small"),
            "High-Qual": st.column_config.TextColumn("HQ", width="small"),
            "Ext_Colab_%": st.column_config.NumberColumn(
                "Inter-inst. Index",
                width="small",
                format="%.0f%%"
            ),
            "DOI": st.column_config.LinkColumn("DOI", width="small", display_text=r"https://doi\.org/(.*)")
        },
        column_order=("Year", "Title", "Authors", "Journal", "Citations", "1st", "Corr.", "High-Qual", "Ext_Colab_%", "DOI")
    )

st.markdown("<style>table { width: 100%; border-bottom: 1px solid #f0f2f6; font-size: 1.1rem; }</style>", unsafe_allow_html=True)






