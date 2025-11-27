"""
Streamlit app: GeoJSON ↔ CSV bulk properties editor workflow
Includes:
- Step 0: Combine multiple GeoJSON
- Step A: GeoJSON → CSV
- Step B: CSV → Merge → GeoJSON
- Step C: Stand-alone Join Attributes (CSV/XLSX/GeoJSON) - IMPROVED VERSION
- XLSX fallback friendly + auto convert join key to string
"""

import streamlit as st
import pandas as pd
import json
import io
from typing import List, Dict, Any

st.set_page_config(page_title="GeoJSON ↔ CSV Bulk Editor", layout="wide")
st.title("GeoJSON ↔ CSV Bulk Editor — bulk-edit properties for uMap workflow")

DEFAULT_EXAMPLE_PATH = "/mnt/data/baee1fac-2f34-4d13-a83e-39ceda97409b.png"

st.info("🚨 **PENTING**: Jangan edit kolom `geometry_json` di Excel. Hanya edit kolom properties (nama, jenis, dsb).")

# --------------------------
# --- IMPROVED Helper functions -----
# --------------------------

def read_csv_with_fallback(file_buffer):
    """Improved CSV reader with better encoding handling"""
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='utf-8', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: UTF-8")
        return df
    except UnicodeDecodeError:
        st.warning("❌ UTF-8 gagal, mencoba Latin-1...")
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='latin-1', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: Latin-1")
        return df
    except UnicodeDecodeError:
        st.warning("❌ Latin-1 gagal, mencoba CP1252...")
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='cp1252', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: CP1252")
        return df
    except Exception as e:
        st.error(f"❌ Semua encoding gagal: {e}")
        return None

def read_xlsx_with_fallback(file_buffer):
    """Improved XLSX reader with better error handling"""
    try:
        file_buffer.seek(0)
        df = pd.read_excel(file_buffer, dtype=str, keep_default_na=False)
        st.success("✅ XLSX berhasil dibaca")
        return df
    except Exception as e:
        st.error(f"❌ Gagal membaca XLSX: {e}")
        return None

def geojson_to_dataframe(geojson: Dict[str, Any]) -> pd.DataFrame:
    """Convert GeoJSON to DataFrame with improved handling"""
    features = geojson.get("features", [])
    rows = []
    for i, feat in enumerate(features):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", None)
        fid = feat.get("id", f"feature_{i}")
        
        # Create row with all properties
        row = {"_feature_id": fid, "geometry_json": json.dumps(geom) if geom else ""}
        
        # Add all properties
        for k, v in props.items():
            row[k] = v
            
        rows.append(row)
    
    if not rows:
        return pd.DataFrame()
        
    df = pd.DataFrame(rows)
    
    # Reorder columns to have _feature_id and geometry_json first
    cols = ["_feature_id", "geometry_json"] + [c for c in df.columns if c not in ("_feature_id", "geometry_json")]
    return df[cols]

def dataframe_to_geojson(df: pd.DataFrame) -> Dict[str, Any]:
    """Convert DataFrame back to GeoJSON"""
    features = []
    for _, row in df.iterrows():
        geom_json = row.get("geometry_json", "")
        try:
            geom = json.loads(geom_json) if pd.notna(geom_json) and geom_json and geom_json.strip() else None
        except:
            geom = None
            
        # Create properties from all columns except geometry and feature_id
        props = {}
        for col in df.columns:
            if col not in ("geometry_json", "_feature_id"):
                value = row[col]
                if pd.notna(value) and value != "":
                    props[col] = value
        
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geom,
            "id": row.get("_feature_id")
        })
    
    return {"type": "FeatureCollection", "features": features}

def combine_geojson_files(geojson_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    all_features = []
    feature_ids = set()
    for geojson_obj in geojson_files:
        for feature in geojson_obj.get("features", []):
            original_id = feature.get("id")
            if original_id and original_id in feature_ids:
                counter = 1
                new_id = f"{original_id}_{counter}"
                while new_id in feature_ids:
                    counter += 1
                    new_id = f"{original_id}_{counter}"
                feature["id"] = new_id
                st.warning(f"⚠️ Duplicate ID '{original_id}' renamed to '{new_id}'")
            if feature.get("id"):
                feature_ids.add(feature["id"])
            all_features.append(feature)
    return {"type":"FeatureCollection","features":all_features}

def clean_dataframe(df):
    """Clean DataFrame by replacing empty values and standardizing"""
    if df is None:
        return None
        
    df = df.copy()
    df = df.replace(['', 'NaN', 'NaT', 'None', 'nan', 'N/A'], None)
    df = df.fillna('')
    
    # Convert all columns to string for consistency
    for col in df.columns:
        df[col] = df[col].astype(str)
        
    return df

def join_attributes(main_df, add_df, join_key):
    """Improved join function with better handling"""
    if main_df is None or add_df is None:
        return None
        
    # Clean both dataframes
    main_df = clean_dataframe(main_df)
    add_df = clean_dataframe(add_df)
    
    # Check if join key exists
    if join_key not in main_df.columns:
        st.error(f"❌ Key '{join_key}' tidak ditemukan di file utama. Kolom yang tersedia: {list(main_df.columns)}")
        return None
        
    if join_key not in add_df.columns:
        st.error(f"❌ Key '{join_key}' tidak ditemukan di file tambahan. Kolom yang tersedia: {list(add_df.columns)}")
        return None
    
    # Convert join key to string in both dataframes
    main_df[join_key] = main_df[join_key].astype(str).str.strip()
    add_df[join_key] = add_df[join_key].astype(str).str.strip()
    
    st.write(f"🔍 Sample join keys dari file utama: {main_df[join_key].head().tolist()}")
    st.write(f"🔍 Sample join keys dari file tambahan: {add_df[join_key].head().tolist()}")
    
    # Perform the join
    joined = pd.merge(main_df, add_df, on=join_key, how="left", suffixes=('', '_add'))
    
    # Remove duplicate columns
    for col in joined.columns:
        if col.endswith('_add'):
            original_col = col[:-4]
            if original_col in joined.columns:
                # Keep the original from main_df, drop the _add version
                joined = joined.drop(columns=[col])
    
    st.success(f"✅ Join berhasil! {len(main_df)} records digabung dengan {len(add_df)} records")
    return joined

# --------------------------
# --- Step 0: Combine GeoJSON
# --------------------------
st.header("🔄 Step 0 — Combine Multiple GeoJSON Files")
multi_geojson_files = st.file_uploader(
    "Upload multiple GeoJSON files (.geojson or .json)", 
    type=["geojson", "json"], 
    key="multi_geo",
    accept_multiple_files=True
)
if multi_geojson_files and len(multi_geojson_files) > 1:
    geojson_objects = []
    valid_files = True
    for uploaded_file in multi_geojson_files:
        try:
            geojson_obj = json.load(uploaded_file)
            if geojson_obj.get("type") == "FeatureCollection":
                geojson_objects.append(geojson_obj)
            else:
                st.error(f"❌ File {uploaded_file.name} bukan FeatureCollection")
                valid_files = False
        except Exception as e:
            st.error(f"❌ File {uploaded_file.name} error: {e}")
            valid_files = False
    if valid_files and geojson_objects:
        combined_geojson = combine_geojson_files(geojson_objects)
        st.success(f"✅ Combined {len(geojson_objects)} files ({len(combined_geojson['features'])} features)")
        st.session_state.combined_geojson = combined_geojson

# --------------------------
# --- Step A: GeoJSON → CSV
# --------------------------
st.header("📥 Step A — Convert GeoJSON → CSV")
col1, col2 = st.columns([1,1])
with col1:
    uploaded_geojson = st.file_uploader("Upload GeoJSON (.geojson or .json)", type=["geojson", "json"], key="upload_geo")
    paste_geo_text = st.text_area("Atau paste GeoJSON di sini (optional)", height=120)
with col2:
    st.write("📋 Instructions:\n- Upload GeoJSON asli → CSV untuk bulk edit\n- Jangan edit geometry_json\n- Bisa pakai combined GeoJSON dari Step 0")

geojson_obj = None
if 'combined_geojson' in st.session_state:
    geojson_obj = st.session_state.combined_geojson
elif uploaded_geojson is not None:
    try: 
        geojson_obj = json.load(uploaded_geojson)
        st.success("✅ GeoJSON berhasil dimuat")
    except Exception as e: 
        st.error(f"❌ Gagal parse GeoJSON: {e}")
elif paste_geo_text.strip() != "":
    try: 
        geojson_obj = json.loads(paste_geo_text)
        st.success("✅ GeoJSON dari teks berhasil dimuat")
    except Exception as e: 
        st.error(f"❌ Gagal parse GeoJSON dari teks: {e}")

if geojson_obj:
    df_out = geojson_to_dataframe(geojson_obj)
    if not df_out.empty:
        st.dataframe(df_out.head(10))
        csv_buffer = io.StringIO()
        df_out.to_csv(csv_buffer, index=False, encoding='utf-8')
        st.download_button("💾 Download CSV untuk diedit", csv_buffer.getvalue().encode("utf-8"), "export_properties.csv", "text/csv")
    else:
        st.warning("⚠️ GeoJSON tidak mengandung features atau kosong")

# --------------------------
# --- Step B: CSV → Merge → GeoJSON
# --------------------------
st.markdown("---")
st.header("📤 Step B — Upload CSV hasil edit → Merge → Download GeoJSON")
edited_csv = st.file_uploader("Upload CSV hasil edit (Step A)", type=["csv"], key="upload_csv")
if edited_csv:
    df_edited = read_csv_with_fallback(edited_csv)
    if df_edited is not None:
        df_edited = df_edited.replace(['','NaN','NaT','None'], None)
        geo_out = dataframe_to_geojson(df_edited)
        st.download_button("💾 Download merged GeoJSON", json.dumps(geo_out, indent=2, ensure_ascii=False).encode("utf-8"), "merged.geojson", "application/json")

# --------------------------
# --- IMPROVED Step C: Stand-alone Join Attributes
# --------------------------
st.header("🧩 Step C — Join Attributes (GeoJSON + CSV)")

st.info("""
**Cara penggunaan:**
1. **File Utama**: Upload GeoJSON Anda
2. **File Tambahan**: Upload file XLSX/CSV dengan data atribut tambahan  
3. **Join Key**: Kolom yang sama di kedua file (biasanya 'id' atau '_feature_id')
""")

col1, col2 = st.columns(2)
with col1:
    st.subheader("File Utama (GeoJSON)")
    main_file = st.file_uploader("Upload file GeoJSON", type=["geojson","json"], key="main_file_fixed")
    
with col2:
    st.subheader("File Tambahan (CSV)")
    add_file = st.file_uploader("Upload file data tambahan", type=["csv"], key="add_file_fixed")

# Auto-detect join key options
join_key_options = ["id", "_feature_id", "name", "ID", "Id"]
join_key_c = st.selectbox("Pilih kolom untuk join:", options=join_key_options, index=0, key="join_key_c_fixed")
custom_join_key = st.text_input("Atau masukkan nama kolom manual:", key="custom_join_key")

# Use custom key if provided
final_join_key = custom_join_key if custom_join_key else join_key_c

if st.button("🔗 JOIN ATTRIBUTES", type="primary", key="join_button_fixed"):
    if not main_file or not add_file:
        st.error("❌ Harap upload kedua file")
    else:
        try:
            # Load MAIN file (GeoJSON)
            st.write("📁 **Memproses File Utama (GeoJSON)...**")
            main_geo = json.load(main_file)
            main_df = geojson_to_dataframe(main_geo)
            
            if main_df.empty:
                st.error("❌ File GeoJSON utama kosong atau tidak valid")
            else:
                st.write(f"✅ GeoJSON loaded: {len(main_df)} features")
                st.write("📊 Kolom dalam GeoJSON:", list(main_df.columns))
                
            # Load ADDITIONAL file (XLSX/CSV)
            st.write("📁 **Memproses File Tambahan...**")
            add_df = None
            if add_file.name.lower().endswith(".csv"):
                add_df = read_csv_with_fallback(add_file)
            elif add_file.name.lower().endswith(".xlsx"):
                add_df = read_xlsx_with_fallback(add_file)
            
            if add_df is None or add_df.empty:
                st.error("❌ File tambahan tidak dapat dibaca atau kosong")
            else:
                st.write(f"✅ Data tambahan loaded: {len(add_df)} records")
                st.write("📊 Kolom dalam file tambahan:", list(add_df.columns))
            
            # Perform join if both files loaded successfully
            if main_df is not None and not main_df.empty and add_df is not None and not add_df.empty:
                df_joined = join_attributes(main_df, add_df, final_join_key)
                
                if df_joined is not None:
                    st.success("🎉 JOIN BERHASIL!")
                    
                    # Show preview
                    st.subheader("📋 Preview Data Hasil Join")
                    st.dataframe(df_joined.head(10))
                    
                    # Show join statistics
                    matched_count = len(df_joined[df_joined[final_join_key].isin(add_df[final_join_key])])
                    st.write(f"📈 Statistik Join: {matched_count}/{len(main_df)} features berhasil dipasangkan")
                    
                    # Download options
                    st.subheader("💾 Download Hasil Join")
                    
                    # CSV Download
                    csv_buffer = io.StringIO()
                    df_joined.to_csv(csv_buffer, index=False, encoding='utf-8')
                    st.download_button(
                        "📥 Download sebagai CSV", 
                        csv_buffer.getvalue().encode("utf-8"), 
                        "joined_data.csv", 
                        "text/csv"
                    )
                    
                    # GeoJSON Download
                    geojson_result = dataframe_to_geojson(df_joined)
                    geojson_str = json.dumps(geojson_result, indent=2, ensure_ascii=False)
                    st.download_button(
                        "🗺️ Download sebagai GeoJSON", 
                        geojson_str.encode("utf-8"), 
                        "joined_data.geojson", 
                        "application/json"
                    )
                    
        except Exception as e:
            st.error(f"❌ Error selama proses join: {str(e)}")
            st.write("🔧 **Tips troubleshooting:**")
            st.write("- Pastikan nama kolom join key sama di kedua file")
            st.write("- Pastikan nilai di kolom join key cocok (case-sensitive)")
            st.write("- Cek preview data di atas untuk memastikan formatnya sesuai")

# Additional debugging info
if st.checkbox("🔧 Show debug info"):
    if 'main_df' in locals():
        st.write("Main DataFrame info:", main_df.info())
    if 'add_df' in locals():
        st.write("Add DataFrame info:", add_df.info())

st.markdown("---")
st.write("**Catatan:** Aplikasi ini khusus untuk menggabungkan data XLSX/CSV dengan GeoJSON berdasarkan kolom join yang sama.")

# --------------------------
# --- STEP D: BULK HTML STYLING FOR PIPE-SEPARATED DATA
# --------------------------
st.markdown("---")
st.header("🎨 Step D — Bulk HTML Styling for Pipe-Separated Data")

st.info("Bulk styling untuk data pipe-separated: Upload CSV, pilih kolom, setiap cell akan di-styling otomatis")

# Pilih sumber data
st.subheader("📁 Pilih Sumber Data")

data_source = st.radio(
    "Pilih sumber data:",
    ["Gunakan data dari Step C", "Upload CSV baru"],
    index=0
)

current_df = None

if data_source == "Gunakan data dari Step C":
    if 'df_joined_c' in st.session_state and st.session_state.df_joined_c is not None:
        current_df = st.session_state.df_joined_c
        st.success(f"✅ Menggunakan data dari Step C ({len(current_df)} records)")
    else:
        st.warning("⚠️ Tidak ada data dari Step C. Silakan upload CSV baru.")
        data_source = "Upload CSV baru"

if data_source == "Upload CSV baru" or current_df is None:
    uploaded_csv = st.file_uploader("Upload CSV file untuk styling", type=["csv"], key="html_styling_csv")
    if uploaded_csv:
        current_df = read_csv_with_fallback(uploaded_csv)
        if current_df is not None:
            st.success(f"✅ CSV berhasil dimuat ({len(current_df)} records)")

# Process styling jika ada data
if current_df is not None:
    st.subheader("🎯 Pilih Kolom untuk Styling")
    
    st.write("**Preview Data:**")
    st.dataframe(current_df.head(5))
    
    # Get text columns
    text_columns = [col for col in current_df.columns 
                   if col not in ['_feature_id', 'geometry_json', 'geometry'] 
                   and current_df[col].dtype == 'object']
    
    if text_columns:
        selected_columns = st.multiselect(
            "Pilih kolom yang berisi data pipe-separated:",
            options=text_columns,
            help="Pilih kolom dengan format: Field1: Value1 | Field2: Value2 | ..."
        )
        
        if selected_columns:
            st.write(f"Selected {len(selected_columns)} columns for styling")
            
            # Preview
            st.subheader("👁️ Preview Sebelum & Sesudah Styling")
            
            preview_row = st.slider("Pilih baris untuk preview:", 0, min(5, len(current_df)-1), 0)
            
            for col in selected_columns[:2]:
                st.write(f"**Kolom:** `{col}`")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    original_value = current_df.iloc[preview_row][col]
                    st.text_area(
                        "Data Asli:", 
                        value=original_value, 
                        height=100, 
                        key=f"orig_{col}_{preview_row}"
                    )
                
                with col2:
                    html_output = process_pipe_separated_data(current_df.iloc[preview_row][col])
                    if html_output:
                        st.components.v1.html(html_output, height=200, scrolling=True)
                        with st.expander("Lihat HTML Code"):
                            st.code(html_output, language='html')
                    else:
                        st.info("Tidak ada data untuk di-styling")
            
            # Bulk processing
            if st.button("🚀 APPLY BULK HTML STYLING", type="primary"):
                with st.spinner(f"Memproses {len(current_df)} records..."):
                    df_styled = bulk_apply_html_styling(current_df, selected_columns)
                    
                    if df_styled is not None:
                        st.session_state.df_styled_final = df_styled
                        st.success(f"✅ Berhasil memproses {len(current_df)} records!")
                        
                        # Show results
                        st.subheader("📊 Hasil Styling")
                        
                        # Show comparison
                        comparison_cols = []
                        for col in selected_columns[:3]:
                            comparison_cols.extend([col, f"{col}_styled"])
                        
                        if comparison_cols:
                            st.dataframe(df_styled[comparison_cols].head(5))
                        
                        # Download options
                        st.subheader("💾 Download Hasil")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            csv_full = io.StringIO()
                            df_styled.to_csv(csv_full, index=False, encoding='utf-8')
                            st.download_button(
                                "📥 Download Full CSV", 
                                csv_full.getvalue().encode("utf-8"), 
                                "styled_data_full.csv", 
                                "text/csv"
                            )
                        
                        with col2:
                            styled_cols = [col for col in df_styled.columns if col.endswith('_styled')]
                            original_ids = [col for col in ['_feature_id', 'id'] if col in df_styled.columns]
                            
                            if styled_cols:
                                df_only_styled = df_styled[original_ids + styled_cols]
                                csv_styled = io.StringIO()
                                df_only_styled.to_csv(csv_styled, index=False, encoding='utf-8')
                                st.download_button(
                                    "🎨 Download Styled Columns Only", 
                                    csv_styled.getvalue().encode("utf-8"), 
                                    "only_styled_columns.csv", 
                                    "text/csv"
                                )
                        
                        with col3:
                            if '_feature_id' in df_styled.columns and 'geometry_json' in df_styled.columns:
                                geojson_output = dataframe_to_geojson(df_styled)
                                geo_str = json.dumps(geojson_output, indent=2, ensure_ascii=False)
                                st.download_button(
                                    "🗺️ Download as GeoJSON", 
                                    geo_str.encode("utf-8"), 
                                    "styled_data.geojson", 
                                    "application/json"
                                )
    else:
        st.warning("⚠️ Tidak ditemukan kolom teks untuk di-styling")

# Quick HTML converter
st.markdown("---")
st.header("🔧 Quick HTML Converter")

test_input = st.text_area(
    "Test konversi data pipe-separated ke HTML:",
    value="Nama Fasilitas: Kantor Perbekel Desa Pidpid | Kecamatan: Abang | Desa: Pidpid | Banjar: Pidpid Kelod | Jenis Fasum: Wantilan | Daya Tampung: 300 orang | Fasilitas Pendukung: toilet, listrik, sumber air, dapur umum",
    height=150
)

if st.button("🔄 Convert to HTML"):
    if test_input.strip():
        html_result = process_pipe_separated_data(test_input)
        st.components.v1.html(html_result, height=400, scrolling=True)
        with st.expander("Lihat HTML Code"):
            st.code(html_result, language='html')
    else:
        st.warning("Masukkan data terlebih dahulu")

st.markdown("---")
st.write("**✨ Complete GeoJSON ↔ CSV Editor with Bulk HTML Styling**")

