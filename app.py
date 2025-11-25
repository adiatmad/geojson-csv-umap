"""
Streamlit app: GeoJSON <-> CSV bulk properties editor workflow
Simplified encoding handling: UTF-8 first, then fallback to Latin-1/CP1252
"""

import streamlit as st
import pandas as pd
import json
import io
from typing import List, Dict, Any

st.set_page_config(page_title="GeoJSON ↔ CSV Bulk Editor", layout="wide")
st.title("GeoJSON ↔ CSV Bulk Editor — bulk-edit properties for uMap workflow")

# Developer-provided local path from conversation history (placeholder)
DEFAULT_EXAMPLE_PATH = "/mnt/data/baee1fac-2f34-4d13-a83e-39ceda97409b.png"

st.info("🚨 **PENTING**: Jangan edit kolom `geometry_json` di Excel. Hanya edit kolom properties (nama, jenis, dsb).")

# --- Simplified Encoding Helpers ---

def read_csv_with_fallback(file_buffer):
    """
    Simple encoding fallback: 
    1. First try UTF-8
    2. If fails, try Latin-1 or CP1252
    """
    # Try UTF-8 first
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='utf-8', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: UTF-8")
        return df
    except UnicodeDecodeError:
        st.warning("❌ UTF-8 gagal, mencoba Latin-1...")
    
    # Try Latin-1 (ISO-8859-1)
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='latin-1', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: Latin-1 (ISO-8859-1)")
        return df
    except UnicodeDecodeError:
        st.warning("❌ Latin-1 gagal, mencoba CP1252...")
    
    # Try CP1252 (Windows Western European)
    try:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, encoding='cp1252', dtype=str, keep_default_na=False)
        st.success("✅ CSV dibaca dengan encoding: CP1252 (Windows)")
        return df
    except Exception as e:
        st.error(f"❌ Semua encoding gagal: {e}")
        raise

def geojson_to_dataframe(geojson: Dict[str, Any]) -> pd.DataFrame:
    """Convert GeoJSON FeatureCollection to pandas DataFrame.
    Each row = 1 feature.
    properties are flattened (kept as columns). geometry is stored as JSON string in 'geometry_json'.
    Also include an 'id' column if available (feature['id']) or create one.
    """
    features = geojson.get("features", [])
    rows = []
    for i, feat in enumerate(features):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", None)
        fid = feat.get("id", f"feature_{i}")
        row = {
            "_feature_id": fid,
            "geometry_json": json.dumps(geom) if geom is not None else None,
        }
        # merge props
        for k, v in props.items():
            # avoid collisions with internal columns
            if k in row:
                row[f"prop_{k}"] = v
            else:
                row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    # ensure deterministic column order
    cols = ["_feature_id", "geometry_json"] + [c for c in df.columns if c not in ("_feature_id", "geometry_json")]
    return df[cols]

def dataframe_to_geojson(df: pd.DataFrame) -> Dict[str, Any]:
    """Convert DataFrame back to GeoJSON FeatureCollection.
    Expects 'geometry_json' column containing a JSON geometry for each row.
    All other columns are treated as properties (except internal ones starting with underscore).
    """
    features = []
    for _, row in df.iterrows():
        geom_json = row.get("geometry_json")
        try:
            geom = json.loads(geom_json) if pd.notna(geom_json) and geom_json is not None else None
        except Exception as e:
            st.error(f"Invalid geometry JSON for feature id={row.get('_feature_id')}: {str(e)}")
            geom = None

        props = {}
        for col in df.columns:
            if col in ("geometry_json", "_feature_id"):
                continue
            # convert NaN to None
            val = row[col]
            if pd.isna(val) or val == '':
                continue
            props[col] = val

        feature = {
            "type": "Feature",
            "properties": props,
            "geometry": geom,
            "id": row.get("_feature_id")
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}

# --- UI: Step 1: Upload GeoJSON and convert to CSV ---
st.header("📥 Step A — Convert GeoJSON → CSV (for bulk editing)")
col1, col2 = st.columns([1, 1])
with col1:
    uploaded_geojson = st.file_uploader("Upload GeoJSON (.geojson or .json)", type=["geojson", "json"], key="upload_geo")
    st.caption("Jika Anda tidak memiliki GeoJSON, Anda dapat paste teks di bawah atau gunakan contoh path dari conversation history.")
    example_path = st.text_input("(Optional) Local example path (from conversation history)", value=DEFAULT_EXAMPLE_PATH)
    paste_geo_text = st.text_area("Atau paste GeoJSON di sini (optional)", height=120)
with col2:
    st.write("📋 Instructions:")
    st.markdown("""
- Upload GeoJSON FeatureCollection asli Anda
- Tool akan membuat CSV di mana setiap baris adalah satu feature
- Kolom `geometry_json` berisi geometry sebagai JSON string — **jangan edit kolom ini di Excel**
- Hanya edit kolom properties di Excel, lalu upload kembali CSV di Step B untuk merge
""")

geojson_obj = None
if uploaded_geojson is not None:
    try:
        geojson_obj = json.load(uploaded_geojson)
        st.success("✅ GeoJSON berhasil di-load")
    except Exception as e:
        st.error(f"❌ Gagal parse GeoJSON: {e}")
elif paste_geo_text.strip() != "":
    try:
        geojson_obj = json.loads(paste_geo_text)
        st.success("✅ GeoJSON dari teks berhasil di-load")
    except Exception as e:
        st.error(f"❌ Gagal parse GeoJSON dari teks: {e}")
else:
    st.caption(f"Contoh lokal path (tidak otomatis dimuat): {example_path}")

if geojson_obj is not None:
    try:
        df_out = geojson_to_dataframe(geojson_obj)
        st.subheader("👀 Preview CSV hasil convert (10 baris pertama)")
        st.dataframe(df_out.head(10))
        
        st.info(f"📊 Total features: {len(df_out)} | Total kolom: {len(df_out.columns)}")

        # CSV download
        csv_buffer = io.StringIO()
        df_out.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        
        st.download_button(
            "💾 Download CSV untuk diedit di Excel", 
            data=csv_bytes, 
            file_name="export_properties.csv", 
            mime="text/csv",
            help="Simpan file CSV ini dan edit di Excel. Untuk menghindari masalah encoding, save sebagai UTF-8!"
        )
        
    except Exception as e:
        st.error(f"❌ Gagal convert GeoJSON → CSV: {e}")

# --- UI: Step 2: Upload edited CSV and merge back to GeoJSON ---
st.markdown("---")
st.header("📤 Step B — Upload CSV hasil edit → Merge → Download GeoJSON")

edited_csv = st.file_uploader("Upload CSV yang sudah diedit (dari Step A)", type=["csv"], key="upload_csv")

if edited_csv is not None:
    try:
        # Use simple fallback approach
        df_edited = read_csv_with_fallback(edited_csv)
        
        st.subheader("👀 Preview CSV (setelah edit)")
        st.dataframe(df_edited.head(10))
        
        st.info(f"📊 Data shape: {df_edited.shape[0]} baris, {df_edited.shape[1]} kolom")

        # Enhanced validation
        if "geometry_json" not in df_edited.columns:
            st.error("❌ CSV tidak mengandung kolom 'geometry_json'. Pastikan file berasal dari Step A dan jangan hapus kolom ini.")
        else:
            # Check for empty geometry columns
            empty_geometry_count = df_edited['geometry_json'].isna().sum() + (df_edited['geometry_json'] == '').sum()
            if empty_geometry_count > 0:
                st.warning(f"⚠️  {empty_geometry_count} features memiliki geometry yang kosong")
            
            # Clean data
            df_edited = df_edited.replace(['', 'NaN', 'NaT', 'None'], None)
            df_edited = df_edited.where(pd.notna(df_edited), None)
            
            # Merge back to GeoJSON
            geo_out = dataframe_to_geojson(df_edited)

            st.subheader("🔍 Preview GeoJSON (feature pertama)")
            if len(geo_out.get("features", [])) > 0:
                st.json(geo_out.get("features")[0])
            else:
                st.warning("Tidak ada features dalam GeoJSON hasil")

            # Download GeoJSON
            geo_str = json.dumps(geo_out, indent=2, ensure_ascii=False)
            st.download_button(
                "💾 Download merged GeoJSON", 
                data=geo_str.encode("utf-8"), 
                file_name="merged.geojson", 
                mime="application/json"
            )
            st.success("✅ GeoJSON berhasil dibuat! Silakan download dan upload ke uMap.")
            
    except Exception as e:
        st.error(f"❌ Gagal memproses CSV: {e}")
        
        # Show encoding help
        st.info("""
        💡 **Tips Encoding**:
        - **Excel**: File → Save As → pilih "CSV UTF-8 (Comma delimited)"
        - **Google Sheets**: File → Download → Comma-separated values
        - **Text Editor**: Save dengan encoding UTF-8
        """)

# --- Enhanced Tips Section ---
st.markdown("---")
st.header("🔧 Tips & Panduan")

st.write("### 🛠️ Cara menghindari masalah encoding di Excel:")
st.markdown("""
1. **Windows**: File → Save As → pilih "CSV UTF-8 (Comma delimited)" 
2. **Mac**: File → Export → pilih "Windows Comma Separated (.csv)"
3. **Atau gunakan text editor** seperti Notepad++/VS Code untuk save sebagai UTF-8
""")

st.write("### 📝 Tips penting:")
st.markdown("""
- ✅ **Boleh edit**: Semua kolom kecuali `geometry_json` dan `_feature_id`
- ❌ **Jangan edit**: Kolom `geometry_json` dan `_feature_id`
- 🔧 **Jika butuh edit geometry**: Gunakan QGIS, uMap editor, atau tools GIS lainnya
- 📁 **Simpan backup** CSV original sebelum edit
""")

# Simple troubleshooting
with st.expander("🔍 Troubleshooting Cepat"):
    st.markdown("""
    **Problem**: Error encoding seperti `utf-8 codec can't decode byte 0xb1`
    
    **Solusi**: 
    1. Buka CSV di text editor (Notepad++, VS Code, dll)
    2. File → Save As → pilih encoding UTF-8
    3. Upload ulang file yang sudah disave sebagai UTF-8
    """)

st.caption("App dengan simplified encoding handling — UTF-8 → Latin-1 → CP1252 fallback")
