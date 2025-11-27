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
# --- Step C: IMPROVED Stand-alone Join Attributes
# --------------------------
st.markdown("---")
st.header("🧩 Step C — Stand-alone Join Attributes (IMPROVED)")
st.info("Upload two files (CSV/XLSX/GeoJSON) and join by a shared key column")

col1, col2 = st.columns(2)
with col1:
    st.subheader("File Utama")
    main_file = st.file_uploader("Upload MAIN file", type=["csv","xlsx","geojson","json"], key="main_file")
with col2:
    st.subheader("File Tambahan") 
    add_file = st.file_uploader("Upload ADDITIONAL file", type=["csv","xlsx","geojson","json"], key="add_file")

# Join key selection with auto-detection
join_key_options = ["id", "_feature_id", "name", "ID", "Id"]
join_key_c = st.selectbox("Pilih kolom untuk join:", options=join_key_options, index=0, key="join_key_c")
custom_join_key = st.text_input("Atau masukkan nama kolom manual:", key="custom_join_key")
final_join_key = custom_join_key if custom_join_key else join_key_c

if st.button("🔗 Join Attributes (Step C - IMPROVED)", type="primary", key="join_button_improved"):
    if not main_file or not add_file:
        st.error("❌ Both files must be uploaded")
    else:
        try:
            # Load MAIN file
            main_df = None
            if main_file.name.lower().endswith(".csv"):
                main_df = read_csv_with_fallback(main_file)
            elif main_file.name.lower().endswith(".xlsx"):
                main_df = read_xlsx_with_fallback(main_file)
            else:  # GeoJSON
                main_geo = json.load(main_file)
                main_df = geojson_to_dataframe(main_geo)

            # Load ADDITIONAL file
            add_df = None
            if add_file.name.lower().endswith(".csv"):
                add_df = read_csv_with_fallback(add_file)
            elif add_file.name.lower().endswith(".xlsx"):
                add_df = read_xlsx_with_fallback(add_file)
            else:  # GeoJSON
                add_geo = json.load(add_file)
                add_df = geojson_to_dataframe(add_geo)

            # Validate loaded data
            if main_df is None or main_df.empty:
                st.error("❌ File utama tidak dapat dibaca atau kosong")
            elif add_df is None or add_df.empty:
                st.error("❌ File tambahan tidak dapat dibaca atau kosong")
            else:
                st.write(f"✅ File utama: {len(main_df)} records, kolom: {list(main_df.columns)}")
                st.write(f"✅ File tambahan: {len(add_df)} records, kolom: {list(add_df.columns)}")
                
                # Perform join
                df_joined_c = join_attributes(main_df, add_df, final_join_key)
                
                if df_joined_c is not None:
                    # Show results
                    st.subheader("📋 Hasil Join")
                    st.dataframe(df_joined_c.head(10))
                    
                    # Show join statistics
                    matched_count = len(df_joined_c[df_joined_c[final_join_key].isin(add_df[final_join_key])])
                    st.write(f"📈 Statistik: {matched_count}/{len(main_df)} records berhasil dipasangkan")
                    
                    # Download options
                    col_dl1, col_dl2 = st.columns(2)
                    
                    with col_dl1:
                        # Download CSV
                        csv_buffer_c = io.StringIO()
                        df_joined_c.to_csv(csv_buffer_c, index=False, encoding='utf-8')
                        st.download_button(
                            "💾 Download CSV after join", 
                            csv_buffer_c.getvalue().encode("utf-8"), 
                            "joined_attributes_stepC.csv", 
                            "text/csv"
                        )
                    
                    with col_dl2:
                        # Download GeoJSON if main was GeoJSON
                        if main_file.name.lower().endswith(("geojson","json")):
                            geojson_out_c = dataframe_to_geojson(df_joined_c)
                            geo_str_c = json.dumps(geojson_out_c, indent=2, ensure_ascii=False)
                            st.download_button(
                                "🗺️ Download GeoJSON after join", 
                                geo_str_c.encode("utf-8"), 
                                "joined_attributes_stepC.geojson", 
                                "application/json"
                            )

        except Exception as e:
            st.error(f"❌ Failed to join attributes: {e}")
            st.write("🔧 **Troubleshooting tips:**")
            st.write("- Pastikan nama kolom join key sama di kedua file")
            st.write("- Pastikan tipe data di kolom join key cocok")
            st.write("- Cek preview data untuk memastikan formatnya sesuai")

# --------------------------
# --- Debug Information (Optional)
# --------------------------
if st.checkbox("🔧 Show Debug Information"):
    st.subheader("Debug Info")
    st.write("Session state keys:", list(st.session_state.keys()))
    
    if 'combined_geojson' in st.session_state:
        st.write("Combined GeoJSON features:", len(st.session_state.combined_geojson['features']))

st.markdown("---")
st.write("**✨ Aplikasi GeoJSON ↔ CSV Editor** - Semua fitur tersedia dengan Step C yang sudah diperbaiki!")
