import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from thefuzz import fuzz
import unicodedata
import re
import io

# ==========================================
# 1. CONFIGURACIÓN E INTERFAZ (ESTILO ESPEJO)
# ==========================================
st.set_page_config(page_title="Academic Performance Auditor - Group", layout="wide")

# Estilo CSS para la tabla
st.markdown("<style>table { width: 100%; border-bottom: 1px solid #f0f2f6; font-size: 1.1rem; }</style>", unsafe_allow_html=True)

col_tit, col_logo = st.columns([6, 1])
with col_logo:
    try: 
        st.image("Logo.png", use_container_width=True)
    except: 
        pass
with col_tit:
    st.markdown('<h1 style="font-size: 38px; margin-bottom: 0px;">Academic Performance Auditor</h1>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 18px; color: #5E5E5E; font-style: italic;">By Social Behavior and Artificial Intelligence Laboratory & Sonora Institute of Technology </p>', unsafe_allow_html=True)

st.write(" ")
archivos_subidos = st.file_uploader("Upload Researchers CSV files:", type=["csv"], accept_multiple_files=True)

def limpiar_titulo(t):
    if not t or pd.isna(t): return ""
    t = unicodedata.normalize('NFKD', str(t)).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z]', '', t)

if archivos_subidos:
    base_datos_cruda = []
    nombres_autores_grupo = []
    
    # --- PASO 1: CARGA INICIAL Y LIMPIEZA ---
    for arc in archivos_subidos:
        try:
            df_inv = pd.read_csv(arc).fillna("")
            nombre_autor = arc.name.replace("Publications_", "").replace(".csv", "").replace("_", " ")
            nombres_autores_grupo.append(nombre_autor)
            
            for _, row in df_inv.iterrows():
                reg = row.to_dict()
                reg['1st'] = nombre_autor if str(reg.get('1st', '')).upper() == 'X' else ""
                reg['Corr.'] = nombre_autor if str(reg.get('Corr.', '')).upper() == 'X' else ""
                hq_val = str(reg.get('High-Qual', '')).strip()
                reg['High-Qual'] = "X" if hq_val.upper() == "X" else ""
                base_datos_cruda.append(reg)
        except: 
            pass

    # --- PASO 2: FILTRADO Y GESTIÓN DE DUPLICADOS ---
    obras_unicas, obras_duplicadas, dois_vistos = [], [], set()
    base_datos_cruda.sort(key=lambda x: x.get('Year', 0), reverse=True)

    for art in base_datos_cruda:
        doi = str(art.get('DOI', '')).lower().strip()
        titulo_c = limpiar_titulo(art.get('Title', ''))
        es_duplicado, idx_e = False, -1
        if doi and doi not in ["nan", "none", "", " "]:
            if doi in dois_vistos:
                es_duplicado = True
                for i, ya in enumerate(obras_unicas):
                    if str(ya.get('DOI', '')).lower().strip() == doi: 
                        idx_e = i
                        break
        if not es_duplicado and titulo_c:
            for i, ya in enumerate(obras_unicas):
                if fuzz.ratio(titulo_c, limpiar_titulo(ya.get('Title', ''))) > 90:
                    es_duplicado = True
                    idx_e = i
                    break
        if not es_duplicado:
            obras_unicas.append(art)
            if doi and doi not in ["nan", ""]: 
                dois_vistos.add(doi)
        else:
            obras_duplicadas.append(art)
            if art['1st'] and art['1st'] not in str(obras_unicas[idx_e]['1st']):
                ex_1 = obras_unicas[idx_e]['1st']
                obras_unicas[idx_e]['1st'] = f"{ex_1}, {art['1st']}" if ex_1 else art['1st']
            if art['Corr.'] and art['Corr.'] not in str(obras_unicas[idx_e]['Corr.']):
                ex_c = obras_unicas[idx_e]['Corr.']
                obras_unicas[idx_e]['Corr.'] = f"{ex_c}, {art['Corr.']}" if ex_c else art['Corr.']

    df_grupo = pd.DataFrame(obras_unicas)
    df_dups = pd.DataFrame(obras_duplicadas)

    # --- CÁLCULOS PREVIOS PARA REPORTES ---
    total_obras = len(df_grupo)
    total_citas = df_grupo['Citations'].sum() if not df_grupo.empty else 0
    trabajos_por_autor = [df_grupo[df_grupo['Authors'].str.contains(n, case=False, na=False)].shape[0] for n in nombres_autores_grupo]
    avg_works, sd_works = np.mean(trabajos_por_autor), np.std(trabajos_por_autor)
    citas_lista = df_grupo['Citations'].tolist() if not df_grupo.empty else [0]
    avg_cites, sd_cites = np.mean(citas_lista), np.std(citas_lista)
    
    col_c_idx = next((c for c in df_grupo.columns if any(x in c for x in ['Institutional', 'Ext_Colab', 'Inter-inst'])), None)
    
    # --- BOTONES DE DESCARGA (DEBAJO DEL UPLOADER) ---
    st.write(" ")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        csv_data = df_grupo.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="Download Database",
            data=csv_data,
            file_name="Publication_Group.csv",
            mime="text/csv",
            key="btn_csv_top"
        )
    with col_d2:
        buffer = io.StringIO()
        buffer.write("ACADEMIC PERFORMANCE AUDITOR - GROUP SUMMARY REPORT\n" + "="*50 + "\n")
        buffer.write(f"Total Authors: {len(nombres_autores_grupo)}\n")
        buffer.write(f"Total Unique Works: {total_obras}\n")
        buffer.write(f"Total Citations: {total_citas}\n")
        buffer.write(f"Avg. Works per Author: {avg_works:.2f} (SD: {sd_works:.2f})\n")
        buffer.write(f"Avg. Citations per Paper: {avg_cites:.2f} (SD: {sd_cites:.2f})\n\n")

        buffer.write("HISTORICAL PERFORMANCE (BY YEAR)\n" + "-"*50 + "\n")
        df_temp_y = df_grupo.copy()
        df_temp_y['Year'] = pd.to_numeric(df_temp_y['Year'], errors='coerce')
        df_temp_y = df_temp_y.dropna(subset=['Year'])
        for yr in sorted(df_temp_y['Year'].unique(), reverse=True):
            df_yr = df_temp_y[df_temp_y['Year'] == yr]
            hq_y = df_yr[df_yr['High-Qual'] == 'X']
            std_y = df_yr[df_yr['High-Qual'] != 'X']
            buffer.write(f"YEAR {int(yr)}:\n")
            buffer.write(f"  - High-Impact: {len(hq_y)} articles, {hq_y['Citations'].sum()} cites\n")
            buffer.write(f"  - Standard: {len(std_y)} articles, {std_y['Citations'].sum()} cites\n\n")

        buffer.write("INDIVIDUAL AUTHOR PERFORMANCE BREAKDOWN\n" + "-"*50 + "\n")
        for aut in nombres_autores_grupo:
            df_a = df_grupo[df_grupo['Authors'].str.contains(aut, case=False, na=False)]
            hq_a = df_a[df_a['High-Qual'] == 'X']
            std_a = df_a[df_a['High-Qual'] != 'X']
            buffer.write(f"AUTHOR: {aut}\n")
            buffer.write(f"  - High-Impact: {len(hq_a)} total (1st: {len(hq_a[hq_a['1st'].str.contains(aut, case=False, na=False)])}, Corr: {len(hq_a[hq_a['Corr.'].str.contains(aut, case=False, na=False)])})\n")
            buffer.write(f"  - Standard: {len(std_a)} total (1st: {len(std_a[std_a['1st'].str.contains(aut, case=False, na=False)])}, Corr: {len(std_a[std_a['Corr.'].str.contains(aut, case=False, na=False)])})\n")
            buffer.write(f"  - Citations: {hq_a['Citations'].sum()} (HQ) / {std_a['Citations'].sum()} (STD)\n")
            buffer.write(f"  - Networking (Avg Colab): {df_a[col_c_idx].mean() if col_c_idx else 0:.1f}%\n")
            buffer.write(f"  - APC Investment Ratio: {(len(df_a[df_a['Author_Cost'] == 'APC Paid']) / len(df_a) * 100) if len(df_a) > 0 else 0:.1f}%\n")
            buffer.write("-" * 30 + "\n")

        buffer.write("\nReport generated by Social Behavior and Artificial Intelligence Laboratory\n")
        st.download_button(
            label="Download Report",
            data=buffer.getvalue(),
            file_name="Extended_Group_Report.txt",
            mime="text/plain",
            key="btn_txt_top"
        )

    # --- PASO 3: MÉTRICAS VISUALES ---
    st.markdown("---")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Authors", len(archivos_subidos))
    m2.metric("Total Works", total_obras)
    m3.metric("Total Cites", total_citas)
    m4.metric("Avg. Works/Auth", f"{avg_works:.1f} ({sd_works:.1f})")
    m5.metric("Avg. Cites/Paper", f"{avg_cites:.1f} ({sd_cites:.1f})")

    # --- PASO 4: DONAS FILA 1 ---
    st.write(" ")
    B31, B32, B33 = st.columns(3)
    n_high = len(df_grupo[df_grupo['High-Qual'] == 'X'])
    c_high = df_grupo[df_grupo['High-Qual'] == 'X']['Citations'].sum()

    for col, tit, vals, clrs, tot in zip([B31, B32, B33], ["Articles", "Citations", "Articles Cost Model"],
        [[n_high, total_obras-n_high], [c_high, total_citas-c_high], [len(df_grupo[df_grupo['Author_Cost']=='No APC']), len(df_grupo[df_grupo['Author_Cost']=='APC Paid'])]],
        [['#28a745', '#dc3545'], ['#28a745', '#dc3545'], ['#2F4F4F','#FFD700']], [total_obras, total_citas, total_obras]):
        
        with col:
            fig = go.Figure(data=[go.Pie(labels=["High-Impact", "Standard"] if "Cost" not in tit else ["No APC", "APC"], values=vals, hole=.6, marker_colors=clrs)])
            fig.update_layout(annotations=[dict(text=f'Total<br>{tot}', x=0.5, y=0.5, font_size=18, showarrow=False)], height=230, margin=dict(t=30,b=10,l=0,r=0), showlegend=True)
            st.subheader(tit)
            st.plotly_chart(fig, use_container_width=True)

    # --- PASO 5: DONAS FILA 2 ---
    st.write(" ")
    B41, B42, B43 = st.columns(3)
    df_hq = df_grupo[df_grupo['High-Qual'] == 'X']
    df_std = df_grupo[df_grupo['High-Qual'] != 'X']
    for col, tit, df_t, clrs in zip([B41, B42, B43], ["High-Impact Journals", "Standard Journals", "Networking"], [df_hq, df_std, df_grupo], [['#003366', '#336699', '#A9A9A9'], ['#003366', '#336699', '#A9A9A9'], ['#27ae60', '#e74c3c', '#A9A9A9']]):
        with col:
            n_t = len(df_t)
            if tit == "Networking":
                c_idx = next((c for c in df_t.columns if any(x in c for x in ['Institutional', 'Ext_Colab', 'Inter-inst'])), None)
                v1, v2 = (len(df_t[df_t[c_idx] < 100]), len(df_t[df_t[c_idx] == 100])) if c_idx and c_idx in df_t.columns else (0,0)
                v3, lbls = 0, ['Cross-inst.', 'Institutional', 'No-id']
            else:
                v1, v2 = len(df_t[df_t['1st'] != ""]), len(df_t[df_t['Corr.'] != ""])
                v3, lbls = max(0, n_t - v1 - v2), ['1st Author', 'Corr. Author', 'Co-author']
            fig = go.Figure(data=[go.Pie(labels=lbls, values=[v1, v2, v3], hole=.6, marker_colors=clrs)])
            fig.update_layout(annotations=[dict(text=f'Total<br>{n_t}', x=0.5, y=0.5, font_size=18, showarrow=False)], height=230, margin=dict(t=30,b=10,l=0,r=0), showlegend=True)
            st.subheader(tit)
            st.plotly_chart(fig, use_container_width=True)
        
    # --- PASO 5.5: ANÁLISIS TEMPORAL (2x2) ---
    st.markdown("---")
    st.subheader("Temporal Group Productivity and Impact")
    df_temp = df_grupo.copy()
    df_temp['Year'] = pd.to_numeric(df_temp['Year'], errors='coerce')
    df_temp = df_temp.dropna(subset=['Year'])
    anios = sorted(df_temp['Year'].unique())
    hq_stats, std_stats = [], []
    for a in anios:
        df_a = df_temp[df_temp['Year'] == a]
        for sub, lista_dest in zip([df_a[df_a['High-Qual'] == 'X'], df_a[df_a['High-Qual'] != 'X']], [hq_stats, std_stats]):
            c_p = [sub[sub['Authors'].str.contains(aut, case=False, na=False)].shape[0] for aut in nombres_autores_grupo]
            m_p, se_p = np.mean(c_p) if c_p else 0, (np.std(c_p)/np.sqrt(len(nombres_autores_grupo))) if c_p else 0
            cit_l = sub['Citations'].tolist()
            m_c, se_c = np.mean(cit_l) if cit_l else 0, (np.std(cit_l)/np.sqrt(len(cit_l))) if len(cit_l) > 0 else 0
            lista_dest.append({'Year': a, 'TotP': len(sub), 'AvgP': m_p, 'SEP': se_p, 'TotC': sub['Citations'].sum(), 'AvgC': m_c, 'SEC': se_c})
    d1, d2 = pd.DataFrame(hq_stats), pd.DataFrame(std_stats)

    def crear_grafico_t(titulo, y_hq, y_std, label_y, se_hq=None, se_std=None):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d1['Year'], y=y_hq, mode='lines+markers', name="High-Impact Journal", line=dict(color='#28a745', width=3)))
        if se_hq is not None:
            fig.add_trace(go.Scatter(x=pd.concat([d1['Year'], d1['Year'][::-1]]), y=pd.concat([y_hq + se_hq, (y_hq - se_hq)[::-1]]), fill='toself', fillcolor='rgba(40,167,69,0.1)', line=dict(color='rgba(255,255,255,0)'), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=d2['Year'], y=y_std, mode='lines+markers', name="Standard Journal", line=dict(color='#dc3545', width=3)))
        if se_std is not None:
            fig.add_trace(go.Scatter(x=pd.concat([d2['Year'], d2['Year'][::-1]]), y=pd.concat([y_std + se_std, (y_std - se_std)[::-1]]), fill='toself', fillcolor='rgba(220,53,69,0.1)', line=dict(color='rgba(255,255,255,0)'), showlegend=False, hoverinfo="skip"))
        fig.update_layout(title=titulo, xaxis=dict(title="Year", nticks=5), yaxis=dict(title=label_y, nticks=5), height=350, margin=dict(t=50, b=20, l=0, r=0), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        return fig

    c1, c2 = st.columns(2)
    with c1: 
        st.plotly_chart(crear_grafico_t("Total Articles", d1['TotP'], d2['TotP'], "Total Articles"), use_container_width=True)
    with c2: 
        st.plotly_chart(crear_grafico_t("Avg. Articles per Author", d1['AvgP'], d2['AvgP'], "Mean Articles", d1['SEP'], d2['SEP']), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3: 
        st.plotly_chart(crear_grafico_t("Total Citations", d1['TotC'], d2['TotC'], "Total Cites"), use_container_width=True)
    with c4: 
        st.plotly_chart(crear_grafico_t("Avg. Citations per Article", d1['AvgC'], d2['AvgC'], "Mean Cites", d1['SEC'], d2['SEC']), use_container_width=True)

    # --- PASO 5.6: PRODUCTIVIDAD POR AUTOR ---
    st.markdown("---")
    st.subheader("Author Productivity & Authorship")
    datos_aut = []
    for aut in nombres_autores_grupo:
        df_a = df_grupo[df_grupo['Authors'].str.contains(aut, case=False, na=False)]
        hq_t = len(df_a[df_a['High-Qual'] == 'X'])
        hq_1 = len(df_a[(df_a['High-Qual'] == 'X') & (df_a['1st'].str.contains(aut, case=False, na=False))])
        hq_c = len(df_a[(df_a['High-Qual'] == 'X') & (df_a['Corr.'].str.contains(aut, case=False, na=False))])
        st_t = len(df_a[df_a['High-Qual'] != 'X'])
        st_1 = len(df_a[(df_a['High-Qual'] != 'X') & (df_a['1st'].str.contains(aut, case=False, na=False))])
        st_c = len(df_a[(df_a['High-Qual'] != 'X') & (df_a['Corr.'].str.contains(aut, case=False, na=False))])
        datos_aut.append({'Author': aut, 'HQ Total': hq_t, 'HQ 1st': hq_1, 'HQ Corr': hq_c, 'STD Total': st_t, 'STD 1st': st_1, 'STD Corr': st_c})
    df_p_aut = pd.DataFrame(datos_aut)

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        df_h_p = df_p_aut.sort_values('HQ Total', ascending=True)
        fig_b1 = go.Figure()
        fig_b1.add_trace(go.Bar(y=df_h_p['Author'], x=df_h_p['HQ Corr'], name='Corr. Author HQ', orientation='h', marker_color='#a5d6a7'))
        fig_b1.add_trace(go.Bar(y=df_h_p['Author'], x=df_h_p['HQ 1st'], name='1st Author HQ', orientation='h', marker_color='#2e7d32'))
        fig_b1.add_trace(go.Bar(y=df_h_p['Author'], x=df_h_p['HQ Total'], name='Total HQ', orientation='h', marker_color='#1b5e20'))
        fig_b1.update_layout(title="High-Impact Journal Productivity", barmode='group', height=400 + (len(nombres_autores_grupo) * 30), xaxis=dict(title="Total Articles"), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, traceorder="reversed"), yaxis={'categoryorder':'trace'})
        st.plotly_chart(fig_b1, use_container_width=True)
    with col_b2:
        df_s_p = df_p_aut.sort_values('STD Total', ascending=True)
        fig_b2 = go.Figure()
        fig_b2.add_trace(go.Bar(y=df_s_p['Author'], x=df_s_p['STD Corr'], name='Corr. Author STD', orientation='h', marker_color='#ef9a9a'))
        fig_b2.add_trace(go.Bar(y=df_s_p['Author'], x=df_s_p['STD 1st'], name='1st Author STD', orientation='h', marker_color='#d32f2f'))
        fig_b2.add_trace(go.Bar(y=df_s_p['Author'], x=df_s_p['STD Total'], name='Total STD', orientation='h', marker_color='#b71c1c'))
        fig_b2.update_layout(title="Standard Journal Productivity", barmode='group', height=400 + (len(nombres_autores_grupo) * 30), xaxis=dict(title="Total Articles"), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, traceorder="reversed"), yaxis={'categoryorder':'trace'})
        st.plotly_chart(fig_b2, use_container_width=True)

    # --- PASO 5.7 Y 5.8: CITAS, COLABORACIÓN Y APC ---
    st.markdown("---")
    st.subheader("Citations, Collaboration and APC")
    datos_c, datos_e = [], []
    for aut in nombres_autores_grupo:
        df_a = df_grupo[df_grupo['Authors'].str.contains(aut, case=False, na=False)]
        datos_c.append({'Author': aut, 'Cites HQ': df_a[df_a['High-Qual'] == 'X']['Citations'].sum(), 'Cites STD': df_a[df_a['High-Qual'] != 'X']['Citations'].sum()})
        datos_e.append({'Author': aut, 'Colab': df_a[col_c_idx].mean() if col_c_idx else 0, 'APC': (len(df_a[df_a['Author_Cost'] == 'APC Paid']) / len(df_a) * 100) if len(df_a) > 0 else 0})
    df_c_aut, df_e_aut = pd.DataFrame(datos_c), pd.DataFrame(datos_e)

    c_c1, c_c2 = st.columns(2)
    with c_c1: 
        fig_c1 = go.Figure(data=[go.Bar(y=df_c_aut.sort_values('Cites HQ', ascending=True)['Author'], x=df_c_aut.sort_values('Cites HQ', ascending=True)['Cites HQ'], orientation='h', marker_color='#28a745')])
        fig_c1.update_layout(title="Citations in High-Impact Journals", height=400 + (len(nombres_autores_grupo) * 25))
        st.plotly_chart(fig_c1, use_container_width=True)
    with c_c2: 
        fig_c2 = go.Figure(data=[go.Bar(y=df_c_aut.sort_values('Cites STD', ascending=True)['Author'], x=df_c_aut.sort_values('Cites STD', ascending=True)['Cites STD'], orientation='h', marker_color='#dc3545')])
        fig_c2.update_layout(title="Citations in Standard Journals", height=400 + (len(nombres_autores_grupo) * 25))
        st.plotly_chart(fig_c2, use_container_width=True)
    
    c_e1, c_e2 = st.columns(2)
    with c_e1: 
        fig_e1 = go.Figure(data=[go.Bar(y=df_e_aut.sort_values('Colab', ascending=True)['Author'], x=df_e_aut.sort_values('Colab', ascending=True)['Colab'], orientation='h', marker_color='#003366')])
        fig_e1.update_layout(title="Collaboration Index (%)", xaxis=dict(range=[0, 100]))
        st.plotly_chart(fig_e1, use_container_width=True)
    with c_e2: 
        fig_e2 = go.Figure(data=[go.Bar(y=df_e_aut.sort_values('APC', ascending=True)['Author'], x=df_e_aut.sort_values('APC', ascending=True)['APC'], orientation='h', marker_color='#FFD700')])
        fig_e2.update_layout(title="Articles with APC (%)", xaxis=dict(range=[0, 100]))
        st.plotly_chart(fig_e2, use_container_width=True)

    # --- PASO 6: TABLAS ---
    st.markdown("---")
    tab1, tab2 = st.tabs(["Unique Published Articles", "Shared Articles"])
    with tab1: 
        st.subheader("Published Articles")
        st.dataframe(df_grupo.sort_values(by=["Year", "Citations"], ascending=[False, False]), use_container_width=True, hide_index=True, height=int((len(df_grupo) * 35) + 120))
    with tab2: 
        st.subheader("Shared articles")
        if not df_dups.empty: 
            st.dataframe(df_dups[["Year", "Title", "Authors", "Journal", "DOI"]], use_container_width=True, hide_index=True)
        else: 
            st.success("No duplicates found.")

