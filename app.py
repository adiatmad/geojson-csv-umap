"""
Streamlit app: GeoJSON ↔ CSV bulk properties editor workflow
Includes:
- Step 0: Combine multiple GeoJSON
- Step A: GeoJSON → CSV
- Step B: CSV → Merge → GeoJSON
- Step C: Stand-alone Join Attributes (CSV ONLY + GeoJSON)
- Improved CSV handling with clear instructions
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
# --- Helper functions -----
# --------------------------

def read_csv_with_fallback(file_buffer):
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
        raise

def geojson_to_dataframe(geojson: Dict[str, Any]) -> pd.DataFrame:
    features = geojson.get("features", [])
    rows = []
    for i, feat in enumerate(features):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", None)
        fid = feat.get("id", f"feature_{i}")
        row = {"_feature_id": fid, "geometry_json": json.dumps(geom) if geom else None}
        for k, v in props.items():
            if k in row:
                row[f"prop_{k}"] = v
            else:
                row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    cols = ["_feature_id", "geometry_json"] + [c for c in df.columns if c not in ("_feature_id", "geometry_json")]
    return df[cols]

def dataframe_to_geojson(df: pd.DataFrame) -> Dict[str, Any]:
    features = []
    for _, row in df.iterrows():
        geom_json = row.get("geometry_json")
        try:
            geom = json.loads(geom_json) if pd.notna(geom_json) and geom_json else None
        except:
            geom = None
        props = {col: row[col] for col in df.columns if col not in ("geometry_json", "_feature_id") and pd.notna(row[col]) and row[col] != ""}
        features.append({"type":"Feature","properties":props,"geometry":geom,"id":row.get("_feature_id")})
    return {"type":"FeatureCollection","features":features}

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

def join_attributes(main_df, add_df, join_key):
    # Convert join key to string in both df
    main_df[join_key] = main_df[join_key].astype(str)
    add_df[join_key] = add_df[join_key].astype(str)
    joined = pd.merge(main_df, add_df, on=join_key, how="left", suffixes=('', '_add'))
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
    try: geojson_obj = json.load(uploaded_geojson)
    except: st.error("❌ Gagal parse GeoJSON")
elif paste_geo_text.strip() != "":
    try: geojson_obj = json.loads(paste_geo_text)
    except: st.error("❌ Gagal parse GeoJSON dari teks")

if geojson_obj:
    df_out = geojson_to_dataframe(geojson_obj)
    st.dataframe(df_out.head(10))
    csv_buffer = io.StringIO()
    df_out.to_csv(csv_buffer, index=False, encoding='utf-8')
    st.download_button("💾 Download CSV untuk diedit", csv_buffer.getvalue().encode("utf-8"), "export_properties.csv", "text/csv")

# --------------------------
# --- Step B: CSV → Merge → GeoJSON
# --------------------------
st.markdown("---")
st.header("📤 Step B — Upload CSV hasil edit → Merge → Download GeoJSON")
edited_csv = st.file_uploader("Upload CSV hasil edit (Step A)", type=["csv"], key="upload_csv")
if edited_csv:
    df_edited = read_csv_with_fallback(edited_csv)
    df_edited = df_edited.replace(['','NaN','NaT','None'], None)
    geo_out = dataframe_to_geojson(df_edited)
    st.download_button("💾 Download merged GeoJSON", json.dumps(geo_out, indent=2, ensure_ascii=False).encode("utf-8"), "merged.geojson", "application/json")

# --------------------------
# --- Step C: Stand-alone Join Attributes (CSV ONLY)
# --------------------------
st.markdown("---")
st.header("🧩 Step C — Join GeoJSON dengan CSV")
st.warning("⚠️ **HANYA UNTUK FILE CSV**: Step ini hanya mendukung file CSV untuk data atribut tambahan!")

col1, col2 = st.columns(2)
with col1:
    st.subheader("File GeoJSON Utama")
    main_file = st.file_uploader("Upload file GeoJSON", type=["geojson","json"], key="main_file")
    
with col2:
    st.subheader("File CSV Data Tambahan") 
    st.info("Pastikan CSV memiliki kolom yang sama dengan GeoJSON untuk join")
    add_file = st.file_uploader("Upload file CSV", type=["csv"], key="add_file")

# Join key selection
if 'main_file' in locals() and main_file and 'add_file' in locals() and add_file:
    try:
        # Load files untuk detect columns
        main_geo = json.load(main_file)
        main_df_temp = geojson_to_dataframe(main_geo)
        
        add_file.seek(0)  # Reset file pointer
        add_df_temp = read_csv_with_fallback(add_file)
        
        # Cari common columns
        common_cols = list(set(main_df_temp.columns) & set(add_df_temp.columns))
        common_cols = [col for col in common_cols if col not in ['geometry_json']]
        
        if common_cols:
            join_key_c = st.selectbox("Pilih kolom untuk join:", options=common_cols, key="join_key_c")
            st.info(f"✅ Kolom umum yang ditemukan: {common_cols}")
        else:
            join_key_c = st.text_input("Masukkan nama kolom join manual:", value="_feature_id", key="join_key_c")
            st.warning("⚠️ Tidak ada kolom umum yang ditemukan, pastikan nama kolom sama di kedua file")
            
    except Exception as e:
        join_key_c = st.text_input("Kolom join key:", value="_feature_id", key="join_key_c")
        st.error(f"Error membaca file: {e}")
else:
    join_key_c = st.text_input("Kolom join key:", value="_feature_id", key="join_key_c")

if st.button("🔗 Join Attributes (Step C)", type="primary"):
    if not main_file or not add_file:
        st.error("❌ Harap upload kedua file (GeoJSON + CSV)")
    else:
        try:
            # Load MAIN (GeoJSON)
            main_file.seek(0)
            main_geo = json.load(main_file)
            main_df = geojson_to_dataframe(main_geo)
            
            # Load ADDITIONAL (CSV)
            add_file.seek(0)
            add_df = read_csv_with_fallback(add_file)
            
            if main_df is None or add_df is None:
                st.error("❌ Gagal memuat salah satu file")
            elif join_key_c not in main_df.columns:
                st.error(f"❌ Key '{join_key_c}' tidak ada di GeoJSON. Kolom yang tersedia: {list(main_df.columns)}")
            elif join_key_c not in add_df.columns:
                st.error(f"❌ Key '{join_key_c}' tidak ada di CSV. Kolom yang tersedia: {list(add_df.columns)}")
            else:
                # Perform join
                df_joined_c = join_attributes(main_df, add_df, join_key_c)
                
                st.success(f"✅ Join berhasil! {len(main_df)} features + {len(add_df)} records CSV")
                
                # Show preview
                st.subheader("📋 Preview Hasil Join")
                st.dataframe(df_joined_c.head(8))
                
                # Download options
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    # Download CSV
                    csv_buffer_c = io.StringIO()
                    df_joined_c.to_csv(csv_buffer_c, index=False, encoding='utf-8')
                    st.download_button(
                        "💾 Download sebagai CSV", 
                        csv_buffer_c.getvalue().encode("utf-8"), 
                        "joined_attributes.csv", 
                        "text/csv"
                    )
                
                with col_dl2:
                    # Download GeoJSON
                    geojson_out_c = dataframe_to_geojson(df_joined_c)
                    geo_str_c = json.dumps(geojson_out_c, indent=2, ensure_ascii=False)
                    st.download_button(
                        "🗺️ Download sebagai GeoJSON", 
                        geo_str_c.encode("utf-8"), 
                        "joined_attributes.geojson", 
                        "application/json"
                    )
                
                # Statistics
                st.info(f"📊 Statistik: {len(main_df.columns)} kolom awal → {len(df_joined_c.columns)} kolom setelah join")

        except Exception as e:
            st.error(f"❌ Gagal melakukan join: {e}")

# --------------------------
# --- INSTRUCTIONS & TROUBLESHOOTING ---
# --------------------------
st.markdown("---")
st.subheader("📋 Panduan Step C - Join GeoJSON dengan CSV")

instructions = """
**Cara menggunakan Step C:**
1. **GeoJSON Utama**: File peta Anda yang berisi geometry
2. **CSV Data Tambahan**: File dengan atribut tambahan yang ingin digabungkan  
3. **Kolom Join**: Pilih kolom yang sama di kedua file (biasanya 'id', '_feature_id', atau 'name')

**Contoh penggunaan:**
- Gabungkan data POI dari CSV dengan geometry dari GeoJSON
- Tambahkan atribut baru dari spreadsheet ke features yang sudah ada
- Update informasi properties dari data eksternal

**Format CSV yang disarankan:**
- Gunakan UTF-8 encoding
- Kolom pertama sebagai header
- Pastikan nilai di kolom join match dengan GeoJSON
"""

st.info(instructions)

st.subheader("❌ Troubleshooting Join")

troubleshooting = """
**Jika join gagal:**
1. **Kolom tidak ditemukan**: Pastikan nama kolom join sama persis di kedua file
2. **Nilai tidak match**: Cek apakah nilai di kolom join cocok (case-sensitive)
3. **Encoding error**: Save CSV sebagai UTF-8
4. **File corrupt**: Pastikan kedua file bisa dibuka normal

**Tips:**
- Gunakan kolom 'id' atau '_feature_id' untuk join yang lebih reliable
- Preview data di Step A untuk melihat struktur GeoJSON
- Test dengan data sample kecil terlebih dahulu
"""

st.warning(troubleshooting)
