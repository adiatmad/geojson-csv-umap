"""
Streamlit app: GeoJSON ↔ CSV bulk properties editor workflow - FIXED VERSION
Includes improved XLSX handling and better join functionality
"""

import streamlit as st
import pandas as pd
import json
import io
from typing import List, Dict, Any

st.set_page_config(page_title="GeoJSON ↔ CSV Bulk Editor - FIXED", layout="wide")
st.title("GeoJSON ↔ CSV Bulk Editor — FIXED VERSION")

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
# --- IMPROVED Step C: Stand-alone Join Attributes
# --------------------------
st.header("🧩 Step C — Join Attributes (CSV + GeoJSON)")

st.info("""
**Cara penggunaan:**
1. **File Utama**: Upload GeoJSON Anda
2. **File Tambahan**: Upload file CSV dengan data atribut tambahan  
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

